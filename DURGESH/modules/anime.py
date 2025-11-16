# anime_tool.py
# Pyrogram tool for existing bot (imports `app` from DURGESH)
# Adds /anime command which fetches AniList and generates a poster

import asyncio
import requests
import textwrap
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from pyrogram import filters
from pyrogram.types import Message

# Import existing pyrogram app from your DURGESH project
from DURGESH import app

# AniList API
ANILIST_API = "https://graphql.anilist.co"


class AnimePosterGenerator:
    def __init__(self, width=1280, height=720):
        self.width = width
        self.height = height

    def search_anime(self, query):
        graphql_query = """
        query ($search: String) {
          Media(search: $search, type: ANIME) {
            id
            title {
              romaji
              english
            }
            coverImage {
              extraLarge
              large
            }
            bannerImage
            genres
            format
            episodes
            season
            seasonYear
            averageScore
            studios {
              nodes {
                name
              }
            }
          }
        }
        """
        variables = {"search": query}
        res = requests.post(ANILIST_API, json={"query": graphql_query, "variables": variables}, timeout=20)
        if res.status_code == 200:
            return res.json().get("data", {}).get("Media")
        return None

    def download_image(self, url):
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        return Image.open(BytesIO(resp.content)).convert("RGBA")

    def create_aesthetic_background(self):
        img = Image.new("RGB", (self.width, self.height))
        draw = ImageDraw.Draw(img)
        for y in range(self.height):
            r = int(60 - (30 * y / self.height))
            g = int(40 - (20 * y / self.height))
            b = int(120 + (60 * y / self.height))
            draw.line([(0, y), (self.width, y)], fill=(r, g, b))
        return img

    def add_fireworks_effect(self, img):
        overlay = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        import math
        fireworks = [
            {'x': 650, 'y': 80, 'color': (255, 180, 100, 180), 'size': 80},
            {'x': 850, 'y': 120, 'color': (255, 100, 200, 180), 'size': 70},
            {'x': 750, 'y': 200, 'color': (100, 200, 255, 180), 'size': 60},
        ]
        for fw in fireworks:
            x, y, color, size = fw['x'], fw['y'], fw['color'], fw['size']
            for angle in range(0, 360, 12):
                end_x = x + int(size * math.cos(math.radians(angle)))
                end_y = y + int(size * math.sin(math.radians(angle)))
                draw.line([(x, y), (end_x, end_y)], fill=color, width=3)
                cs = 4
                draw.ellipse([end_x-cs, end_y-cs, end_x+cs, end_y+cs], fill=color)
        return Image.alpha_composite(img.convert("RGBA"), overlay)

    def generate_poster(self, anime_data):
        base = self.create_aesthetic_background()
        poster = self.add_fireworks_effect(base).convert("RGBA")

        # Add cover if available
        cover_url = anime_data.get("coverImage", {}).get("extraLarge") or anime_data.get("coverImage", {}).get("large")
        if cover_url:
            try:
                cover = self.download_image(cover_url)
                cover = cover.resize((450, 636), Image.Resampling.LANCZOS)
                cover_x = self.width - 480
                cover_y = (self.height - 636) // 2
                poster.paste(cover, (cover_x, cover_y), cover)
            except Exception:
                pass

        # Draw text
        draw = ImageDraw.Draw(poster)
        title = anime_data['title'].get('english') or anime_data['title'].get('romaji') or "Unknown Title"

        # fonts (fallback to default if not found)
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            info_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        except Exception:
            title_font = ImageFont.load_default()
            info_font = ImageFont.load_default()

        # --- LOGO (SYNTAX REALM) ---
        draw.text((40, 30), "SYNTAX REALM", font=info_font, fill=(255, 255, 255))

        # --- TITLE ---
        y_pos = 140
        wrapped = textwrap.wrap(title, width=20)
        for i, line in enumerate(wrapped[:2]):
            # stroke supported on PIL 8+; fallback to plain text if missing
            try:
                draw.text((50, y_pos + i*80), line, font=title_font, fill=(255, 255, 255), stroke_width=2, stroke_fill=(0,0,0))
            except TypeError:
                draw.text((50, y_pos + i*80), line, font=title_font, fill=(255, 255, 255))

        # --- STUDIO / GENRES / SCORE ---
        studio = anime_data.get('studios', {}).get('nodes', [{}])[0].get('name', 'Unknown Studio')
        genres = ', '.join(anime_data.get('genres', [])[:3]) or 'Genres Unknown'
        score = anime_data.get('averageScore')
        info_y = y_pos + 180
        draw.text((50, info_y), f"🎬 {studio}", font=info_font, fill=(255,255,255))
        draw.text((50, info_y + 40), f"🎭 {genres}", font=info_font, fill=(255,255,255))
        if score:
            draw.text((50, info_y + 80), f"⭐ Score: {score}/100", font=info_font, fill=(255,255,255))

        # --- VERTICAL SYNTAX REALM ---
        sidebar_text = "SYNTAX REALM"
        try:
            bbox = draw.textbbox((0, 0), sidebar_text, font=info_font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except Exception:
            # fallback measurement
            text_width, text_height = info_font.getsize(sidebar_text)

        text_img = Image.new('RGBA', (text_width + 20, text_height + 20), (0,0,0,0))
        text_draw = ImageDraw.Draw(text_img)
        try:
            text_draw.text((10,10), sidebar_text, font=info_font, fill=(255,255,255), stroke_width=2, stroke_fill=(0,0,0))
        except TypeError:
            text_draw.text((10,10), sidebar_text, font=info_font, fill=(255,255,255))

        text_img = text_img.rotate(90, expand=True)
        poster.paste(text_img, (self.width - 60, self.height//2 - text_img.height//2), text_img)

        return poster.convert("RGB")


# ---- Handler ----
@app.on_message(filters.command("anime"))
async def anime_command_handler(client, message: Message):
    """
    Usage:
    /anime <anime name>
    Example: /anime Your Name
    """
    # parse query
    args = message.text.split(maxsplit=1)
    if len(args) < 2 or not args[1].strip():
        await message.reply_text("Usage: /anime <anime name>\nExample: /anime One Piece")
        return

    query = args[1].strip()
    status_msg = await message.reply_text(f"🔍 Searching `{query}` and generating poster...")

    gen = AnimePosterGenerator()

    try:
        # run blocking search in thread
        anime_data = await asyncio.to_thread(gen.search_anime, query)
        if not anime_data:
            await status_msg.edit_text("❌ Anime not found on AniList. Try another name.")
            return

        await status_msg.edit_text("🎨 Generating poster...")

        poster = await asyncio.to_thread(gen.generate_poster, anime_data)

        bio = BytesIO()
        poster.save(bio, format="PNG")
        bio.seek(0)

        title = anime_data['title'].get('english') or anime_data['title'].get('romaji') or "Anime Poster"
        caption = ""

        await message.reply_photo(photo=bio, caption=caption)
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}")
