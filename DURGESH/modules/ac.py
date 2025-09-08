import re
import html
import asyncio
from collections import defaultdict
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from DURGESH import app
from config import ADMINS
from DURGESH.database import db

captiondb = db.captions
thumbdb = db.thumbs  # <-- NAYI COLLECTION FOR THUMBS

# -------------------------------------------------
# Regex helpers (unchanged)
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
# THUMB HELPERS (NEW)
# -------------------------------------------------
async def load_thumb(chat_id: str):
    data = await thumbdb.find_one({"chat_id": chat_id})
    return data.get("thumb_id") if data else None

async def save_thumb(chat_id: str, thumb_id: str):
    await thumbdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"thumb_id": thumb_id}},
        upsert=True
    )

async def delete_thumb(chat_id: str):
    await thumbdb.delete_one({"chat_id": chat_id})

# -------------------------------------------------
# Admin check helper
# -------------------------------------------------
def is_admin(uid: int) -> bool:
    return uid in ADMINS

# -------------------------------------------------
# Command handlers
# -------------------------------------------------
@app.on_message(filters.command(["setcaption", "sc"]) & (filters.group | filters.channel))
async def set_caption(client, message: Message):
    if not message.sender_chat and (not message.from_user or not is_admin(message.from_user.id)):
        await message.reply_text("F.ck you")
        return

    chat_id = str(message.chat.id)
    if len(message.command) < 2:
        reply = await message.reply_text(
            "❌ Caption daal bhai.\nExample: `/setcaption <b>{filename}</b>`"
        )
        await asyncio.sleep(60)
        try:
            await message.delete()
            await reply.delete()
        except Exception:
            pass
        return

    caption = message.text.split(None, 1)[1].strip()
    await save_caption(chat_id, caption)
    reply = await message.reply_text("✅ Caption set ho gaya!")
    await asyncio.sleep(60)
    try:
        await message.delete()
        await reply.delete()
    except Exception:
        pass

@app.on_message(filters.command(["getcaption", "gc"]) & (filters.group | filters.channel))
async def get_caption(client, message: Message):
    if not message.sender_chat and (not message.from_user or not is_admin(message.from_user.id)):
        await message.reply_text("F.ck you")
        return

    chat_id = str(message.chat.id)
    caption = await load_caption(chat_id)
    if not caption:
        reply = await message.reply_text("❌ Caption set nahi hai.")
        await asyncio.sleep(60)
        try:
            await message.delete()
            await reply.delete()
        except Exception:
            pass
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
    reply = await message.reply_text(
        f"📝 Current template:\n\n{preview}", parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(60)
    try:
        await message.delete()
        await reply.delete()
    except Exception:
        pass

# -------------------------------------------------
# THUMB COMMANDS (NEW)
# -------------------------------------------------
@app.on_message(filters.command(["setthumb", "st"]) & (filters.group | filters.channel))
async def set_thumb(client, message: Message):
    # sirf admin
    if not message.sender_chat and (not message.from_user or not is_admin(message.from_user.id)):
        await message.reply_text("F.ck you")
        return

    chat_id = str(message.chat.id)

    # ———————————————————————————————————————————————————————————————
    # CHECK: KYA YE COMMAND KISI PHOTO KE REPLY ME DIYA GAYA HAI?
    # ———————————————————————————————————————————————————————————————
    if not message.reply_to_message or not message.reply_to_message.photo:
        reply = await message.reply_text(
            "📸 Bhai — kisi **photo pe reply karke** `/setthumb` likho!\n"
            "Example:\n1. Kisi photo pe reply karo\n2. Type karo: `/setthumb`"
        )
        await asyncio.sleep(60)
        try:
            await message.delete()
            await reply.delete()
        except Exception:
            pass
        return

    # ———————————————————————————————————————————————————————————————
    # AGAR REPLY ME PHOTO HAI → TO USKA FILE_ID SAVE KARO
    # ———————————————————————————————————————————————————————————————
    thumb_id = message.reply_to_message.photo.file_id
    await save_thumb(chat_id, thumb_id)
    reply = await message.reply_text("✅ Thumbnail set ho gaya! Ab har file ke saath ye cover lagega.")
    await asyncio.sleep(60)
    try:
        await message.delete()
        await reply.delete()
    except Exception:
        pass



@app.on_message(filters.command(["delthumb", "dt"]) & (filters.group | filters.channel))
async def del_thumb(client, message: Message):
    if not message.sender_chat and (not message.from_user or not is_admin(message.from_user.id)):
        await message.reply_text("F.ck you")
        return

    chat_id = str(message.chat.id)
    await delete_thumb(chat_id)
    reply = await message.reply_text("🗑️ Thumbnail delete ho gaya!")
    await asyncio.sleep(60)
    try:
        await message.delete()
        await reply.delete()
    except Exception:
        pass

# -------------------------------------------------
# Episode-first, quality-second bulk handler
# -------------------------------------------------
from typing import List, Tuple

bulk_bucket: dict[str, dict[tuple[int, int], list[Message]]] = defaultdict(dict)
BULK_WAIT = 5
LOCK = asyncio.Lock()

def _quality_val(fname: str) -> int:
    txt = fname.upper()
    if "360P" in txt or "360" in txt:
        return 360
    if "480P" in txt or "480" in txt:
        return 480
    if "720P" in txt or "720" in txt:
        return 720
    if "1080P" in txt or "1080" in txt or "FHD" in txt:
        return 1080
    if "4K" in txt or "2160P" in txt or "UHD" in txt:
        return 2160
    return 9999

def _int_episode(fname: str) -> int:
    try:
        raw = extract_episode(fname)
        return int(re.search(r'\d+', raw).group())
    except Exception:
        return 9999

@app.on_message(filters.channel & filters.media)
async def handle_bulk(client, message: Message):
    fname = (
        message.document and message.document.file_name
        or message.video and (message.video.file_name or "Video")
        or message.audio and (message.audio.file_name or "Audio")
        or "Photo"
    )

    ep_num = _int_episode(fname)
    qual   = _quality_val(fname)
    chat_k = str(message.chat.id)

    async with LOCK:
        bucket = bulk_bucket[chat_k]
        bucket.setdefault((ep_num, qual), []).append(message)
        if sum(len(lst) for lst in bucket.values()) == 1:
            asyncio.create_task(_flush_bulk(chat_k, BULK_WAIT))

async def _flush_bulk(chat_k: str, delay: int):
    await asyncio.sleep(delay)

    async with LOCK:
        bucket = bulk_bucket.pop(chat_k, {})
    if not bucket:
        return

    ordered: list[Message] = []
    for (ep, qual), msgs in sorted(bucket.items()):
        ordered.extend(msgs)

    thumb_id = await load_thumb(chat_k)  # Thumbnail load karo

    for msg in ordered:
        custom = await load_caption(chat_k)
        if not custom:
            continue

        filename = None
        filesize = None
        duration = None
        media_type = None
        media_obj = None

        if msg.document:
            filename = msg.document.file_name
            filesize = msg.document.file_size
            media_type = "document"
            media_obj = msg.document
        elif msg.video:
            filename = msg.video.file_name or "Video"
            filesize = msg.video.file_size
            duration = msg.video.duration
            media_type = "video"
            media_obj = msg.video
        elif msg.audio:
            filename = msg.audio.file_name or "Audio"
            filesize = msg.audio.file_size
            duration = msg.audio.duration
            media_type = "audio"
            media_obj = msg.audio
        elif msg.photo:
            # Photo ka alag se handle — caption ke saath bhejna
            filename = "Photo"
            media_type = "photo"
            media_obj = msg.photo

        if not filename or not media_obj:
            continue

        cap = (
            custom
            .replace("{filename}", html.escape(filename.rsplit(".", 1)[0]))
            .replace("{filesize}", html.escape(get_readable_file_size(filesize)))
            .replace("{duration}", html.escape(format_duration(duration)))
            .replace("{quality}", html.escape(extract_quality(filename)))
            .replace("{season}", html.escape(extract_season(filename)))
            .replace("{episode}", html.escape(extract_episode(filename)))
        )

        try:
            # ———————————————————————————————————————————————————————————————
            # AB HUM COPY() NAHI, TYPE KE HISAAB SE SEND KARENGE + THUMB DALENGE
            # ———————————————————————————————————————————————————————————————
            if media_type == "document":
                await app.send_document(
                    chat_id=int(chat_k),
                    document=media_obj.file_id,
                    caption=cap,
                    parse_mode=ParseMode.HTML,
                    thumb=thumb_id  # ✅ DOCUMENT ke saath THUMB kaam karta hai!
                )
            elif media_type == "video":
                # Bada video ke liye document use karo
                if filesize and filesize > 50 * 1024 * 1024:  # 50 MB
                    await app.send_document(
                        chat_id=int(chat_k),
                        document=media_obj.file_id,
                        caption=cap,
                        parse_mode=ParseMode.HTML,
                        thumb=thumb_id
                    )
                else:
                    await app.send_video(
                        chat_id=int(chat_k),
                        video=media_obj.file_id,
                        caption=cap,
                        parse_mode=ParseMode.HTML,
                        thumb=thumb_id
                    )
                            )
            elif media_type == "audio":
                await app.send_audio(
                    chat_id=int(chat_k),
                    audio=media_obj.file_id,
                    caption=cap,
                    parse_mode=ParseMode.HTML,
                    # ❗ Audio ke saath THUMB nahi lagta — ignore
                )
            elif media_type == "photo":
                await app.send_photo(
                    chat_id=int(chat_k),
                    photo=media_obj.file_id,
                    caption=cap,
                    parse_mode=ParseMode.HTML,
                    # Photo ke saath alag se thumb nahi daalte — khud photo hi thumb hai
                )

            # Original delete kardo
            await msg.delete()

        except Exception as e:
            if "FLOOD_WAIT" in str(e):
                wait = int(str(e).split("wait ")[1].split()[0])
                await asyncio.sleep(wait)
            else:
                print("Repost failed:", e)

        await asyncio.sleep(1)
