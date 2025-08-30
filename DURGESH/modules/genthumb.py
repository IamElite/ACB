import aiofiles, aiohttp, asyncio
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import os

# Optional: HD background URL (fallback to solid color)
BACKGROUND_URL = "https://i.imgur.com/8kAXHbW.jpg"  # dark gradient

FONTS_DIR = "fonts"
def font_path(name, size):
    path = os.path.join(FONTS_DIR, name)
    return ImageFont.truetype(path, size) if os.path.isfile(path) else ImageFont.load_default()

async def fetch_bg():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(BACKGROUND_URL) as r:
                return Image.open(BytesIO(await r.read())).resize((720, 1280)).convert("RGB")
    except:
        return Image.new("RGB", (720, 1280), "#111111")

def add_shadow(draw, x, y, text, font, fill, shadow_color="#000000", offset=(3,3)):
    draw.text((x+offset[0], y+offset[1]), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)

async def make_thumb(season: int, episode: int, lang: str) -> bytes:
    W, H = 720, 1280
    img = await fetch_bg()
    draw = ImageDraw.Draw(img)

    # Load fonts
    font_se  = font_path("Montserrat-Bold.ttf", 110)
    font_ep  = font_path("Montserrat-Bold.ttf", 100)
    font_lg  = font_path("Montserrat-SemiBold.ttf", 70)

    # Colors
    accent = "#00c3ff"
    text   = "#ffffff"

    # Text strings
    se_txt = f"SEASON {season}"
    ep_txt = f"EPISODE {episode}"
    lg_txt = lang.upper()

    # Drop-shadow + main text
    add_shadow(draw, 50, 150, se_txt, font_se, accent)
    add_shadow(draw, 50, 150 + 120, ep_txt, font_ep, text)
    lw, lh = draw.textsize(lg_txt, font=font_lg)
    add_shadow(draw, W - lw - 50, H - lh - 100, lg_txt, font_lg, accent)

    # Optional: add rounded corners mask
    mask = Image.new("L", img.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    radius = 40
    mask_draw.rounded_rectangle([(0,0), img.size], radius, fill=255)
    img.putalpha(mask)
    final = Image.new("RGB", img.size, "#000")
    final.paste(img, mask=mask)

    buf = BytesIO()
    final.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf.read()

from DURGESH import app
from pyrogram import filters

@app.on_message(filters.command("gt") & filters.reply)
async def gt_handler(_, msg):
    replied = msg.reply_to_message
    if not replied.photo:
        return await msg.reply("❗️Reply to a photo first.")

    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply("❗️Usage: `/gt 11 221 Hindi`")

    import re
    match = re.match(r"^(\d+)\s+(\d+)(?:\s+(.+))?$", parts[1])
    if not match:
        return await msg.reply("❗️Bad format. Use: `/gt 11 221 Hindi`")

    season, episode, lang = match.groups()
    season, episode = int(season), int(episode)
    lang = lang.strip() if lang else "Hindi"

    thumb_bytes = await make_thumb(season, episode, lang)
    await msg.reply_photo(
        photo=thumb_bytes,
        caption=f"✅ HD Thumbnail\nSeason: {season} | Episode: {episode} | Lang: {lang}"
    )
