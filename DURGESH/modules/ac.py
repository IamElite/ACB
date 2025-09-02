
#   - /setcaption or /st <HTML template> per chat (safe parsing; no IndexError)
#   - /getcaption or /gc shows current template (HTML rendered)
#   - Auto-apply on media (groups/channels), album first item only
#   - Placeholders: {filename} {filesize} {duration} {quality} {season} {episode}

import re
import html
import asyncio
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from DURGESH import app
from config import ADMINS
from DURGESH.database import db

captiondb = db.captions

# -------------------------------------------------
# Helper regex utilities
# -------------------------------------------------
def extract_episode(fname: str) -> str:
    for pat, grp in (
        (r'EPS(\d+)\s*EP(\d+)\s*\((\d+)\)', (2, 3)),
        (r'S(\d+)\s*(?:E|EP)(\d+)\s*\((\d+)\)', (2, 3)),
        (r'S(\d+)\s*(?:E|EP)(\d+)', (2,)),
        (r'(?:E|EP)\s*\((\d+)\)', (1,)),
        (r'-\s*(\d+)', (1,))
    ):
        m = re.search(pat, fname, re.IGNORECASE)
        if m:
            if len(grp) == 2:
                return f"{m.group(grp[0]).zfill(2)} ({m.group(grp[1])})"
            return f"{m.group(grp[0]).zfill(2)}" if grp[0] == 2 else f"({m.group(grp[0])})"
    return "N/A"

def extract_season(fname: str) -> str:
    for pat in (
        r'S(\d+)(?:E|EP)(\d+)', r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)',
        r'S(\d+)[^\d]*(\d+)', r'\bseason\s*(\d+)\b', r'\bs(\d+)\b'
    ):
        m = re.search(pat, fname, re.IGNORECASE)
        if m:
            return m.group(1)
    return "N/A"

def extract_quality(text: str) -> str:
    qpats = [
        (r'[([{<]?\s*4k\s*[)\]}>]?', "4k"),
        (r'[([{<]?\s*2k\s*[)\]}>]?', "2k"),
        (r'[([{<]?\s*4kX264\s*[)\]}>]?', "4kX264"),
        (r'[([{<]?\s*4kx265\s*[)\]}>]?', "4kx265"),
        (r'\bWEB[.\- ]*DL\b', "WEB-DL"),
        (r'[([{<]?\s*HdRip\s*[)\]}>]?|\bHdRip\b', "HdRip"),
        (r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', None)
    ]
    for pat, repl in qpats:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return repl if repl else (m.group(1) or m.group(2))
    return "Unknown"

# -------------------------------------------------
# Formatting helpers
# -------------------------------------------------
def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while size_in_bytes >= 1024 and idx < len(units) - 1:
        size_in_bytes /= 1024
        idx += 1
    return f"{size_in_bytes:.2f} {units[idx]}"

def format_duration(duration) -> str:
    if duration is None:
        return "N/A"
    try:
        secs = int(duration)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    except (ValueError, TypeError):
        return "N/A"

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

# -------------------------------------------------
# DB layer
# -------------------------------------------------
async def load_caption(chat_id: str):
    data = await captiondb.find_one({"chat_id": chat_id})
    return data["caption"] if data else None

async def save_caption(chat_id: str, caption: str):
    await captiondb.update_one(
        {"chat_id": chat_id},
        {"$set": {"caption": caption}},
        upsert=True
    )

# -------------------------------------------------
# Auto-delete utility
# -------------------------------------------------
async def auto_delete_message(message: Message, delay: int = 60):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

# -------------------------------------------------
# Command handlers
# -------------------------------------------------
@app.on_message(filters.command(["setcaption", "sc"]) & (filters.group | filters.channel))
async def set_caption(client, message: Message):
    # Skip admin check if sent by channel itself
    if not message.sender_chat and (not message.from_user or not is_admin(message.from_user.id)):
        await message.reply_text("❌ You are not authorized to use this command.")
        return

    chat_id = str(message.chat.id)
    if len(message.command) < 2:
        reply = await message.reply_text(
            "❌ Please provide a caption after the command.\nExample: `/setcaption <b>{filename}</b>`"
        )
        asyncio.create_task(auto_delete_message(message))
        asyncio.create_task(auto_delete_message(reply))
        return

    caption = message.text.split(None, 1)[1].strip()
    await save_caption(chat_id, caption)
    reply = await message.reply_text("✅ Caption successfully set!")
    asyncio.create_task(auto_delete_message(message))
    asyncio.create_task(auto_delete_message(reply))


@app.on_message(filters.command(["getcaption", "gc"]) & (filters.group | filters.channel))
async def get_caption(client, message: Message):
    if not message.sender_chat and (not message.from_user or not is_admin(message.from_user.id)):
        await message.reply_text("❌ You are not authorized to use this command.")
        return

    chat_id = str(message.chat.id)
    caption = await load_caption(chat_id)
    if not caption:
        reply = await message.reply_text("❌ No caption set for this chat.")
        asyncio.create_task(auto_delete_message(message))
        asyncio.create_task(auto_delete_message(reply))
        return

    preview = (
        caption
        .replace("{filename}", "Example_Filename")
        .replace("{filesize}", "1.23 GB")
        .replace("{duration}", "1:23:45")
        .replace("{quality}", "1080p")
        .replace("{season}", "1")
        .replace("{episode}", "01 (123)")
    )
    reply = await message.reply_text(f"📝 Current caption template:\n\n{preview}", parse_mode=ParseMode.HTML)
    asyncio.create_task(auto_delete_message(message))
    asyncio.create_task(auto_delete_message(reply))

# -------------------------------------------------
# Media handler for channels
# -------------------------------------------------
@app.on_message(filters.channel & filters.media)
async def handle_channel_media(client, message: Message):
    chat_id = str(message.chat.id)
    custom_caption = await load_caption(chat_id)
    if not custom_caption:
        return

    # Extract file info
    filename, filesize, duration = None, None, None
    if message.document:
        filename = message.document.file_name
        filesize = message.document.file_size
    elif message.video:
        filename = message.video.file_name or "Video"
        filesize = message.video.file_size
        duration = message.video.duration
    elif message.audio:
        filename = message.audio.file_name or "Audio"
        filesize = message.audio.file_size
        duration = message.audio.duration
    elif message.photo:
        filename = "Photo"

    if not filename:
        return

    # Fill placeholders
    custom_caption = (
        custom_caption
        .replace("{filename}", html.escape(filename.rsplit(".", 1)[0]))
        .replace("{filesize}", html.escape(get_readable_file_size(filesize)))
        .replace("{duration}", html.escape(format_duration(duration)))
        .replace("{quality}", html.escape(extract_quality(filename)))
        .replace("{season}", html.escape(extract_season(filename)))
        .replace("{episode}", html.escape(extract_episode(filename)))
    )

    try:
        await message.copy(chat_id, caption=custom_caption, parse_mode=ParseMode.HTML)
        await message.delete()
    except Exception as e:
        print(f"Error handling channel media: {e}")
