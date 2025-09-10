import html
import re
import asyncio
from collections import defaultdict
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from DURGESH import app
from DURGESH.database import db

captiondb = db.captions

# ---------------- Helpers ----------------
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
    for pat in (r'S(\d+)(?:E|EP)(\d+)', r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)',
                r'S(\d+)[^\d]*(\d+)', r'\bseason\s*(\d+)\b', r'\bs(\d+)\b'):
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
            q = repl if repl else (m.group(1) or m.group(2))
            if q:
                q = q.lower()
                if "360" in q:
                    return "480p"
                return q
    return "N/A"

def get_readable_file_size(size_in_bytes) -> str:
    if not size_in_bytes:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    while size_in_bytes >= 1024 and idx < len(units) - 1:
        size_in_bytes /= 1024
        idx += 1
    return f"{size_in_bytes:.2f} {units[idx]}"

def format_duration(duration) -> str:
    if not duration:
        return "N/A"
    try:
        secs = int(duration)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    except:
        return "N/A"

# ---------------- Database ----------------
async def load_caption(chat_id: str):
    data = await captiondb.find_one({"chat_id": chat_id})
    return data["caption"] if data else None

async def save_caption(chat_id: str, caption: str):
    await captiondb.update_one({"chat_id": chat_id}, {"$set": {"caption": caption}}, upsert=True)

async def remove_caption(chat_id: str):
    await captiondb.delete_one({"chat_id": chat_id})

# ---------------- Commands ----------------
async def _set_caption(message: Message):
    chat_id = str(message.chat.id)
    if len(message.command) < 2:
        reply = await message.reply_text("❌ Provide caption after command.\nExample: `/setcaption <b>{filename}</b>`")
        await asyncio.sleep(60)
        try: await message.delete(); await reply.delete()
        except: pass
        return
    caption = message.text.split(None, 1)[1].strip()
    await save_caption(chat_id, caption)
    reply = await message.reply_text("✅ Caption saved!")
    await asyncio.sleep(60)
    try: await message.delete(); await reply.delete()
    except: pass

async def _get_caption(message: Message):
    chat_id = str(message.chat.id)
    caption = await load_caption(chat_id)
    if not caption:
        reply = await message.reply_text("❌ No caption set.")
        await asyncio.sleep(60)
        try: await message.delete(); await reply.delete()
        except: pass
        return
    preview = (caption.replace("{filename}", "Example_Filename")
                     .replace("{filesize}", "1.23 GB")
                     .replace("{duration}", "1:23:45")
                     .replace("{quality}", "480p")
                     .replace("{season}", "1")
                     .replace("{episode}", "01 (123)"))
    reply = await message.reply_text(f"📝 Current template:\n\n{preview}", parse_mode=ParseMode.HTML)
    await asyncio.sleep(60)
    try: await message.delete(); await reply.delete()
    except: pass

async def _remove_caption(message: Message):
    chat_id = str(message.chat.id)
    await remove_caption(chat_id)
    reply = await message.reply_text("✅ Caption removed! Auto-captioning disabled.")
    await asyncio.sleep(60)
    try: await message.delete(); await reply.delete()
    except: pass

# Register in groups
@app.on_message(filters.group & filters.command(["setcaption", "sc"]))
async def set_caption_group(client, message: Message): await _set_caption(message)

@app.on_message(filters.group & filters.command(["getcaption", "gc"]))
async def get_caption_group(client, message: Message): await _get_caption(message)

@app.on_message(filters.group & filters.command(["removecaption", "rc", "rmcaption"]))
async def remove_caption_group(client, message: Message): await _remove_caption(message)

# Register in channels
@app.on_message(filters.channel & filters.command(["setcaption", "sc"]))
async def set_caption_channel(client, message: Message): await _set_caption(message)

@app.on_message(filters.channel & filters.command(["getcaption", "gc"]))
async def get_caption_channel(client, message: Message): await _get_caption(message)

@app.on_message(filters.channel & filters.command(["removecaption", "rc", "rmcaption"]))
async def remove_caption_channel(client, message: Message): await _remove_caption(message)

# ---------------- Bulk Handler ----------------
bulk_bucket: dict[str, dict[tuple[int,int], list[Message]]] = defaultdict(dict)
bulk_tasks: dict[str, asyncio.Task] = {}
BULK_WAIT = 3
LOCK = asyncio.Lock()

def _quality_val(fname: str) -> int:
    txt = fname.upper()
    if "360" in txt: return 360
    if "480" in txt: return 480
    if "720" in txt: return 720
    if "1080" in txt or "FHD" in txt: return 1080
    if "4K" in txt or "2160" in txt: return 2160
    return 9999

def _int_episode(fname: str) -> int:
    try:
        raw = extract_episode(fname)
        return int(re.search(r'\d+', raw).group())
    except: return 9999

@app.on_message(filters.media & (filters.group | filters.channel))
async def handle_bulk(client, message: Message):
    chat_id = str(message.chat.id)
    caption = await load_caption(chat_id)
    if not caption: return

    fname = (message.document.file_name if message.document else
             message.video.file_name if message.video else
             message.audio.file_name if message.audio else
             "Photo")
    ep_num = _int_episode(fname)
    qual = _quality_val(fname)

    async with LOCK:
        bucket = bulk_bucket[chat_id]
        bucket.setdefault((ep_num, qual), []).append(message)
        if chat_id in bulk_tasks and not bulk_tasks[chat_id].done():
            bulk_tasks[chat_id].cancel()
        bulk_tasks[chat_id] = asyncio.create_task(_flush_bulk(chat_id, BULK_WAIT))

async def _flush_bulk(chat_id: str, delay: int):
    try: await asyncio.sleep(delay)
    except asyncio.CancelledError: return

    async with LOCK:
        bucket = bulk_bucket.pop(chat_id, {})

    if not bucket: return

    caption = await load_caption(chat_id)
    if not caption: return

    ordered = []
    for (ep, qual), msgs in sorted(bucket.items()):
        ordered.extend(msgs)

    for msg in ordered:
        filename = filesize = duration = None
        if msg.document:
            filename = msg.document.file_name; filesize = msg.document.file_size
        elif msg.video:
            filename = msg.video.file_name or "Video"; filesize = msg.video.file_size; duration = msg.video.duration
        elif msg.audio:
            filename = msg.audio.file_name or "Audio"; filesize = msg.audio.file_size; duration = msg.audio.duration
        elif msg.photo:
            filename = "Photo"

        if not filename: continue

        cap = (caption
               .replace("{filename}", html.escape(filename.rsplit('.',1)[0]))
               .replace("{filesize}", html.escape(get_readable_file_size(filesize)))
               .replace("{duration}", html.escape(format_duration(duration)))
               .replace("{quality}", html.escape(extract_quality(filename)))
               .replace("{season}", html.escape(extract_season(filename)))
               .replace("{episode}", html.escape(extract_episode(filename))))

        try:
            await msg.copy(int(chat_id), caption=cap, parse_mode=ParseMode.HTML)
            await msg.delete()
        except Exception as e:
            if "FLOOD_WAIT" in str(e):
                wait = int(str(e).split("wait ")[1].split()[0])
                await asyncio.sleep(wait)
                try: await msg.copy(int(chat_id), caption=cap, parse_mode=ParseMode.HTML); await msg.delete()
                except: pass
            else: print("Reorder failed:", e)
        await asyncio.sleep(1)
