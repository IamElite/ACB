# plugins/gt.py  (or wherever you keep handlers)

import re
import os
import asyncio
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from pyrogram import filters
from DURGESH import app          # your bot instance

DEFAULT_LANG = "Hindi"
FONTS_DIR = "fonts"

# ---------- helpers ----------
def font_path(name: str, size: int):
    path = os.path.join(FONTS_DIR, name)
    return ImageFont.truetype(path, size) if os.path.isfile(path) else ImageFont.load_default()

def text_size(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def add_shadow(draw: ImageDraw.Draw, x: int, y: int, text: str,
               font: ImageFont.FreeTypeFont, fill: str,
               shadow_color: str = "#000000", offset: tuple = (3, 3)):
    draw.text((x + offset[0], y + offset[1]), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=fill)

# ---------- thumbnail generator ----------
def make_thumb(season: int, episode: int, lang: str) -> bytes:
    W, H = 720, 1280
    img = Image.new("RGB", (W, H), "#111111")
    draw = ImageDraw.Draw(img)

    # fonts
    font_se = font_path("Montserrat-Bold.ttf", 110)
    font_ep = font_path("Montserrat-Bold.ttf", 100)
    font_lg = font_path("Montserrat-SemiBold.ttf", 70)

    # colors
    accent = "#00c3ff"
    text_color = "#ffffff"

    se_txt = f"SEASON {season}"
    ep_txt = f"EPISODE {episode}"
    lg_txt = lang.upper()

    # draw text with shadow
    add_shadow(draw, 50, 150, se_txt, font_se, accent)
    add_shadow(draw, 50, 150 + 120, ep_txt, font_ep, text_color)

    lw, lh = text_size(draw, lg_txt, font_lg)
    add_shadow(draw, W - lw - 50, H - lh - 100, lg_txt, font_lg, accent)

    # binary buffer
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return buf.getvalue()

# ---------- /gt command ----------
@app.on_message(filters.command("gt") & filters.reply)
async def gt_handler(_, msg):
    replied = msg.reply_to_message
    if not replied or not replied.photo:
        return await msg.reply("❗️Reply to a photo first.")

    parts = (msg.text or "").split(maxsplit=1)
    if len(parts) < 2:
        return await msg.reply("❗️Usage: `/gt 11 221 [language]`")

    match = re.match(r"^(\d+)\s+(\d+)(?:\s+(.+))?$", parts[1])
    if not match:
        return await msg.reply("❗️Bad format. Use: `/gt 11 221 Hindi`")

    season, episode, lang = match.groups()
    season, episode = int(season), int(episode)
    lang = lang.strip() if lang else DEFAULT_LANG

    # run blocking PIL code in thread
    thumb_bytes = await asyncio.to_thread(make_thumb, season, episode, lang)

    await msg.reply_photo(
        photo=thumb_bytes,
        caption=f"✅ Thumbnail\nSeason: {season} | Episode: {episode} | Lang: {lang}"
    )
