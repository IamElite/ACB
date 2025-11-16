# anime_thumb_tool.py
# Usage: place in your bot repo, restart bot
# /anime <anime name> -> replies with a 1280x720 thumbnail image (no caption)
#
# Requires: pillow, requests, pyrogram
# pip install pillow requests pyrogram tgcrypto

import asyncio
import textwrap
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from pyrogram import filters
from pyrogram.types import Message

from DURGESH import app  # your existing pyrogram app

ANILIST_API = "https://graphql.anilist.co"
OUT_W, OUT_H = 1280, 720

# ----------------- AniList search -----------------
def search_anime(query, timeout=20):
    graphql = """
    query ($search: String) {
      Media(search: $search, type: ANIME) {
        id
        title { romaji english }
        coverImage { extraLarge large medium }
        bannerImage
        genres
        format
        episodes
        season
        seasonYear
        averageScore
        studios { nodes { name } }
        description(asHtml: false)
      }
    }
    """
    payload = {"query": graphql, "variables": {"search": query}}
    r = requests.post(ANILIST_API, json=payload, timeout=timeout)
    if r.status_code == 200:
        return r.json().get("data", {}).get("Media")
    return None

# ----------------- Thumbnail generator -----------------
class AnimeThumbGenerator:
    def __init__(self, w=OUT_W, h=OUT_H):
        self.w = w
        self.h = h

    def load_image(self, url_or_path, max_size=None):
        if str(url_or_path).lower().startswith("http"):
            r = requests.get(url_or_path, timeout=20)
            r.raise_for_status()
            img = Image.open(BytesIO(r.content)).convert("RGBA")
        else:
            img = Image.open(url_or_path).convert("RGBA")
        if max_size:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
        return img

    def _draw_diamond(self, draw, cx, cy, size, fill):
        half = size // 2
        pts = [(cx, cy-half), (cx+half, cy), (cx, cy+half), (cx-half, cy)]
        draw.polygon(pts, fill=fill)

    def make_thumb(self, anime_data):
        # canvas
        canvas = Image.new("RGB", (self.w, self.h), (248, 247, 250))
        draw = ImageDraw.Draw(canvas)

        # subtle gradient background
        grad = Image.new("L", (self.w, self.h))
        gd = ImageDraw.Draw(grad)
        for y in range(self.h):
            val = int(240 + 15 * (y / self.h))
            gd.line([(0, y), (self.w, y)], fill=val)
        canvas = Image.composite(Image.new("RGB", canvas.size, (245,245,250)), canvas, grad)

        # try load cover image
        cover_url = (anime_data.get("coverImage") or {}).get("extraLarge") or (anime_data.get("coverImage") or {}).get("large")
        if cover_url:
            try:
                src = self.load_image(cover_url, max_size=(900,900))
            except Exception:
                src = None
        else:
            src = None

        # prepare left rotated image (diamond)
        if src:
            w0, h0 = src.size
            side = min(w0, h0)
            left = (w0 - side)//2
            top = (h0 - side)//2
            sq = src.crop((left, top, left+side, top+side)).resize((520,520), Image.Resampling.LANCZOS)
            # rotate square to diamond
            rot = sq.rotate(45, expand=True)
            # mask
            mask = Image.new("L", sq.size, 255).rotate(45, expand=True).filter(ImageFilter.GaussianBlur(0))
            rx, ry = rot.size
            img_x = 80
            img_y = (self.h - ry)//2
            canvas.paste(rot, (img_x, img_y), mask)
            # glow behind
            glow = Image.new("RGBA", canvas.size, (0,0,0,0))
            gdraw = ImageDraw.Draw(glow)
            gx = img_x + rx//2
            gy = img_y + ry//2
            gdraw.ellipse([gx-300, gy-300, gx+300, gy+300], fill=(255,200,220,40))
            canvas = Image.alpha_composite(canvas.convert("RGBA"), glow).convert("RGB")
            draw = ImageDraw.Draw(canvas)

        # diagonal white panel
        panel_w, panel_h = 900, 420
        panel = Image.new("RGBA", (panel_w, panel_h), (255,255,255,255))
        pd = ImageDraw.Draw(panel)
        pd.rectangle([0,0,panel_w-1,panel_h-1], outline=(235,235,238))
        panel = panel.rotate(-18, expand=True)
        px = self.w - 820
        py = (self.h - panel.size[1])//2 - 10
        canvas.paste(panel, (px, py), panel)
        draw = ImageDraw.Draw(canvas)

        # small diamond accents
        acc = ImageDraw.Draw(canvas)
        start_x = px + 60
        start_y = py - 40
        for i, s in enumerate([36,28,20]):
            self._draw_diamond(acc, start_x + i*60, start_y + (i%2)*6, s, (255,192,203))

        # fonts (fallback)
        def f(path, size):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                return ImageFont.load_default()

        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]
        fp = next((p for p in font_paths if p and isinstance(p, str) and __import__("os").path.exists(p)), None)
        title_font = f(fp, 64) if fp else ImageFont.load_default()
        sub_font = f(fp, 18) if fp else ImageFont.load_default()
        desc_font = f(fp, 18) if fp else ImageFont.load_default()
        logo_font = f(fp, 20) if fp else ImageFont.load_default()

        # text area inside panel
        text_x = px + 80
        text_y = py + 40

        title = anime_data.get("title", {}).get("english") or anime_data.get("title", {}).get("romaji") or "Unknown Title"
        subtitle = (anime_data.get("studios", {}).get("nodes", [{}])[0].get("name") or "Studio Unknown")
        genres = ', '.join(anime_data.get("genres", [])[:3]) or "Genres Unknown"
        score = anime_data.get("averageScore")
        desc = anime_data.get("description") or ""

        # draw title
        draw.text((text_x, text_y), title, font=title_font, fill=(30,30,30))

        # subtitle
        draw.text((text_x, text_y + 74), subtitle.upper(), font=sub_font, fill=(120,120,120))

        # description wrapped (max 4 lines)
        wrapped = textwrap.wrap(desc, width=48)
        dy = text_y + 106
        for i, line in enumerate(wrapped[:4]):
            draw.text((text_x, dy + i*26), line, font=desc_font, fill=(80,80,80))

        # small signature/top-right text like example
        sig_x = px + panel.size[0] - 180
        sig_y = py + 20
        draw.text((sig_x, sig_y), f"CV: {title}", font=sub_font, fill=(140,140,140))

        # bottom-left small logo text (SYNTAX REALM)
        draw.text((50, self.h - 50), "SYNTAX REALM", font=logo_font, fill=(90,90,90))

        # subtle vignette
        v = Image.new("L", (self.w, self.h), 0)
        vd = ImageDraw.Draw(v)
        for i in range(400):
            vd.ellipse([-i, -i, self.w+i, self.h+i], fill=int(255 * (i/400)))
        v = v.filter(ImageFilter.GaussianBlur(40))
        canvas = Image.composite(canvas, Image.new("RGB", canvas.size, (10,10,10)), v)

        return canvas

# ----------------- Handler -----------------
@app.on_message(filters.command("anime"))
async def anime_handler(client, message: Message):
    # parse
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.reply_text("Usage: /anime <anime name>\nExample: /anime One Piece")
        return

    query = args[1].strip()
    status = await message.reply_text(f"🔍 Searching `{query}` and creating thumbnail...")
    gen = AnimeThumbGenerator()

    try:
        anime = await asyncio.to_thread(search_anime, query)
        if not anime:
            await status.edit_text("❌ Anime not found on AniList. Try another name.")
            return

        # make thumbnail (blocking)
        thumb = await asyncio.to_thread(gen.make_thumb, anime)

        bio = BytesIO()
        thumb.save(bio, format="PNG", quality=95)
        bio.seek(0)

        # send photo WITHOUT caption (as requested)
        await message.reply_photo(photo=bio)
        await status.delete()
    except Exception as e:
        try:
            await status.edit_text(f"❌ Error: {e}")
        except:
            pass
