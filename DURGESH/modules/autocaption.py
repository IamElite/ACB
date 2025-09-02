# autocaption.py
# Requirements:
#   pyrogram>=2.0 tgcrypto
# Features:
#   - /setcaption <HTML template> per chat (safe parsing; no IndexError)
#   - /getcaption shows current template (HTML rendered)
#   - Auto-apply on media (groups/channels), album first item only
#   - Placeholders: {filename} {filesize} {duration} {quality} {season} {episode}

import re
from typing import Dict, Optional, Tuple

from DURGESH import app  # Pre-configured Pyrogram Client
from pyrogram import filters, enums
from pyrogram.types import Message

# ------------------------- Regex helpers -------------------------

def extract_episode(fname: str) -> Optional[str]:
    m = re.search(r'EPS(\d+)\s*EP(\d+)\s*\((\d+)\)', fname, re.IGNORECASE)
    if m:
        return f"{m.group(2)} ({m.group(3)})"
    m = re.search(r'S(\d+)\s*(?:E|EP)\s*(\d+)\s*\((\d+)\)', fname, re.IGNORECASE)
    if m:
        return f"{m.group(2).zfill(2)} ({m.group(3)})"
    m = re.search(r'S(\d+)\s*(?:E|EP)\s*(\d+)\b', fname, re.IGNORECASE)
    if m:
        return m.group(2).zfill(2)
    m = re.search(r'(?:^|[\s._-])(?:E|EP)\s*\((\d+)\)', fname, re.IGNORECASE)
    if m:
        return f"({m.group(1)})"
    m = re.search(r'[\s._-](\d{1,3})(?:\D|$)', fname)
    if m:
        return m.group(1).zfill(2)
    return None  # [7][8]

def extract_season(fname: str) -> Optional[str]:
    s_pats = [
        r'\bS(\d+)\s*(?:E|EP)\s*\d+\b',
        r'\bS(\d+)\b',
        r'\bseason\s*(\d+)\b',
        r'\bs(\d+)\b',
    ]
    for pat in s_pats:
        m = re.search(pat, fname, re.IGNORECASE)
        if m:
            return m.group(1)
    return None  # [7][8]

def extract_quality(text: str) -> str:
    qpats = [
        (r'\b4k\s*x\s*265\b', "4kx265"),
        (r'\b4k\s*x\s*264\b', "4kx264"),
        (r'\b4k\b', "4k"),
        (r'\b2k\b', "2k"),
        (r'\bWEB[.\- ]*DL\b', "WEB-DL"),
        (r'\bH[DR]Rip\b', "HdRip"),
        (r'\b(\d{3,4})\s*p\b', None),  # 720p, 1080p, 2160p
    ]
    for pat, fixed in qpats:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return fixed if fixed else f"{m.group(1)}p"
    return "Unknown"  # [7][8]

# ------------------------- Message adapters -------------------------

def get_filename_from_msg(msg: Message) -> str:
    if msg.document and msg.document.file_name:
        return msg.document.file_name
    if msg.video and msg.video.file_name:
        return msg.video.file_name
    if msg.audio and msg.audio.file_name:
        return msg.audio.file_name
    if msg.animation and msg.animation.file_name:
        return msg.animation.file_name
    if msg.photo:
        return f"photo_{msg.id}.jpg"
    if msg.voice:
        return f"voice_{msg.id}.ogg"
    return f"file_{msg.id}"  # [9]

def get_filesize_from_msg(msg: Message) -> Optional[int]:
    if msg.document:
        return msg.document.file_size
    if msg.video:
        return msg.video.file_size
    if msg.audio:
        return msg.audio.file_size
    if msg.animation:
        return msg.animation.file_size
    if msg.voice:
        return msg.voice.file_size
    return None  # [9]

def human_size(num_bytes: Optional[int]) -> str:
    if not num_bytes:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    s = float(num_bytes)
    idx = 0
    while s >= 1024 and idx < len(units) - 1:
        s /= 1024.0
        idx += 1
    return f"{s:.2f} {units[idx]}"  # [3]

def get_duration_from_msg(msg: Message) -> Optional[int]:
    if msg.video and msg.video.duration:
        return msg.video.duration
    if msg.audio and msg.audio.duration:
        return msg.audio.duration
    if msg.voice and msg.voice.duration:
        return msg.voice.duration
    return None  # [9]

def fmt_duration(seconds: Optional[int]) -> str:
    if seconds is None:
        return ""
    s = int(seconds)
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:02d}" if h > 0 else f"{m:02d}:{sec:02d}"  # [3]

# ------------------------- Template rendering -------------------------

def render_template(tpl: str, msg: Message) -> str:
    fname = get_filename_from_msg(msg)
    size_bytes = get_filesize_from_msg(msg)
    dur = get_duration_from_msg(msg)

    season = extract_season(fname) or ""
    episode = extract_episode(fname) or ""
    quality = extract_quality(fname) if fname else "Unknown"

    safe = {
        "filename": fname or "",
        "filesize": human_size(size_bytes),
        "duration": fmt_duration(dur),
        "quality": quality,
        "season": season,
        "episode": episode,
        "chat_id": str(msg.chat.id),
        "user_id": str(msg.from_user.id if msg.from_user else ""),
    }
    return re.sub(r"\{(\w+)\}", lambda m: safe.get(m.group(1), ""), tpl)  # [6]

# ------------------------- Bot state -------------------------

caption_templates: Dict[int, str] = {}  # In-memory; prod me DB use karein. [5]
MEDIA_FILTER = (filters.photo | filters.video | filters.document | filters.audio | filters.voice | filters.animation)  # [5]
media_group_first_seen: Dict[str, int] = {}  # Album first-item tracking. [5]

# ------------------------- Commands -------------------------

@app.on_message(filters.command("setcaption") & (filters.group | filters.channel))
async def set_caption_handler(_, message: Message):
    # Robust parsing: maxsplit=1; guard for missing args
    text = message.text or ""
    parts = text.split(None, 1)  # ["cmd", "rest"] or ["cmd"] only
    if len(parts) < 2 or not parts[10].strip():
        await message.reply_text(
            "Usage:\n/setcaption Your HTML template\n\nPlaceholders: {filename} {filesize} {duration} {quality} {season} {episode}",
            quote=True,
        )
        return
    tpl = parts[10].strip()
    caption_templates[message.chat.id] = tpl
    await message.reply_text("Caption template set for this chat.", quote=True)  # [3][4]

@app.on_message(filters.command("getcaption") & (filters.group | filters.channel))
async def get_caption_handler(_, message: Message):
    tpl = caption_templates.get(message.chat.id)
    if tpl:
        await message.reply_text(tpl, quote=True, parse_mode=enums.ParseMode.HTML)
    else:
        await message.reply_text("No template set. Use /setcaption to set one.", quote=True)  # [2]

# ------------------------- Media handler -------------------------

@app.on_message(MEDIA_FILTER & (filters.group | filters.channel))
async def media_auto_caption(client, message: Message):
    tpl = caption_templates.get(message.chat.id)
    if not tpl:
        return

    # Only first item in media albums
    if message.media_group_id:
        mgid = message.media_group_id
        if mgid in media_group_first_seen:
            return
        media_group_first_seen[mgid] = message.id

    filename = get_filename_from_msg(message)
    old_caption = message.caption or ""
    rendered = render_template(tpl, message)

    parts = []
    if filename:
        parts.append(filename)
    if rendered:
        parts.append(rendered)
    if old_caption:
        parts.append(old_caption)

    new_caption = "\n\n".join(parts).strip()
    if new_caption == old_caption:
        return

    try:
        await message.edit_caption(new_caption, parse_mode=enums.ParseMode.HTML)
    except Exception:
        try:
            await client.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.id,
                caption=new_caption,
                parse_mode=enums.ParseMode.HTML,
            )
        except Exception as e2:
            print(f"Edit caption failed: {e2}")  # [1][11][2]
