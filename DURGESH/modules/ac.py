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
authchanneldb = db.auth_channels

# Default caption
DEFAULT_CAPTION = """<blockquote>
╭────────────────────⦿
├ 📺<b>єᴘɪꜱσᴅє</b> ➛ <i>{episode}</i> <b>(ꜱєᴧꜱση</b> <i>{season}</i><b>)</b>
├ 🔊<b>ᴧᴜᴅɪσ</b> ➛ <i>ʜɪηᴅɪ #σꜰꜰɪᴄɪᴧʟ</i>
├ 🎥<b>ǫᴜᴧʟɪᴛʏ</b> ➛ <i>{quality}</i>
├ 🌐<b>[ @TGUrlsHub & @TGEliteHub ]</b>
╰────────────────────⦿
</blockquote>"""

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

# ---------------- Auth Database ----------------
async def add_auth_channel(chat_id: str):
    await authchanneldb.update_one(
        {"chat_id": chat_id},
        {"$set": {"chat_id": chat_id}},
        upsert=True
    )

async def remove_auth_channel(chat_id: str):
    await authchanneldb.delete_one({"chat_id": chat_id})

async def is_channel_authed(chat_id: str) -> bool:
    data = await authchanneldb.find_one({"chat_id": chat_id})
    return bool(data)

async def get_all_auth_channels():
    cursor = authchanneldb.find({})
    return [doc["chat_id"] async for doc in cursor]

# ---------------- Caption Database ----------------
async def load_caption(chat_id: str):
    data = await captiondb.find_one({"chat_id": chat_id})
    return data["caption"] if data else None

async def save_caption(chat_id: str, caption: str):
    await captiondb.update_one({"chat_id": chat_id}, {"$set": {"caption": caption}}, upsert=True)

async def remove_caption(chat_id: str):
    await captiondb.delete_one({"chat_id": chat_id})

# ---------------- Auth Commands ----------------
@app.on_message(filters.command(["capauth", "ca"]) & filters.private)
async def auth_channel_cmd(client, message: Message):
    """Authorize a channel for caption management"""
    
    print(f"🔧 capauth command received from user {message.from_user.id}")
    
    try:
        # Extract channel_id from command or reply
        if len(message.command) == 2:
            channel_id = message.command[1]
            if not channel_id.startswith('-100'):
                if channel_id.startswith('-'):
                    channel_id = f"-100{channel_id.lstrip('-')}"
                else:
                    channel_id = f"-100{channel_id}"
            print(f"📝 Processing channel ID: {channel_id}")
        elif message.reply_to_message and message.reply_to_message.forward_from_chat:
            channel_id = str(message.reply_to_message.forward_from_chat.id)
            print(f"📝 Got channel ID from forwarded message: {channel_id}")
        else:
            return await message.reply_text(
                "❌ **Usage:**\n\n"
                "`/capauth <channel_id>`\n"
                "or\n"
                "`/ca <channel_id>`\n\n"
                "**Example:** `/ca -1001234567890`\n\n"
                "Or reply to a forwarded channel message with `/ca`"
            )
        
        # Try to get chat info to verify
        try:
            chat = await client.get_chat(channel_id)
            chat_name = chat.title or "Unknown"
            print(f"✅ Channel found: {chat_name} ({channel_id})")
        except Exception as e:
            print(f"❌ Error accessing channel: {e}")
            return await message.reply_text(
                f"⚠️ **Error:** Cannot access channel!\n\n"
                f"**Channel ID:** `{channel_id}`\n\n"
                f"**Reason:** {str(e)}\n\n"
                f"**Solution:**\n"
                f"1. Make sure bot is added as admin in the channel\n"
                f"2. Bot needs 'Post Messages' and 'Delete Messages' permissions\n"
                f"3. Check if channel ID is correct"
            )
        
        # Add to auth list
        await add_auth_channel(channel_id)
        print(f"✅ Channel {channel_id} added to auth list")
        
        # Set default caption
        await save_caption(channel_id, DEFAULT_CAPTION)
        print(f"✅ Default caption set for {channel_id}")
        
        await message.reply_text(
            f"✅ **Channel Authorized!**\n\n"
            f"📺 **Channel:** {chat_name}\n"
            f"🆔 **ID:** `{channel_id}`\n\n"
            f"✅ Default caption has been set!\n\n"
            f"**Next Steps:**\n"
            f"• Upload media to channel to test\n"
            f"• Use `/gc {channel_id}` to view caption\n"
            f"• Use `/sc {channel_id} <new_caption>` to change caption"
        )
        
    except Exception as e:
        print(f"❌ Unexpected error in capauth: {e}")
        await message.reply_text(f"❌ **Unexpected Error:** {str(e)}")

@app.on_message(filters.command(["capunauth", "cua"]) & filters.private)
async def unauth_channel_cmd(client, message: Message):
    """Remove channel authorization"""
    
    print(f"🗑️ capunauth command received from user {message.from_user.id}")
    
    try:
        if len(message.command) == 2:
            channel_id = message.command[1]
            if not channel_id.startswith('-100'):
                if channel_id.startswith('-'):
                    channel_id = f"-100{channel_id.lstrip('-')}"
                else:
                    channel_id = f"-100{channel_id}"
        elif message.reply_to_message and message.reply_to_message.forward_from_chat:
            channel_id = str(message.reply_to_message.forward_from_chat.id)
        else:
            return await message.reply_text(
                "❌ **Usage:** `/capunauth <channel_id>` or `/cua <channel_id>`\n\n"
                "**Example:** `/cua -1001234567890`"
            )
        
        await remove_auth_channel(channel_id)
        await remove_caption(channel_id)
        
        await message.reply_text(
            f"✅ **Channel Unauthorized!**\n\n"
            f"🆔 **ID:** `{channel_id}`\n\n"
            f"Caption removed and auto-captioning disabled."
        )
        
        print(f"✅ Channel {channel_id} unauthorized")
        
    except Exception as e:
        print(f"❌ Error in capunauth: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command(["authlist", "al"]) & filters.private)
async def list_auth_channels_cmd(client, message: Message):
    """List all authorized channels"""
    
    print(f"📋 authlist command received from user {message.from_user.id}")
    
    try:
        channels = await get_all_auth_channels()
        
        if not channels:
            return await message.reply_text("⚠️ **No channels authorized yet.**\n\nUse `/capauth <channel_id>` to authorize a channel.")
        
        text = "✅ **Authorized Channels:**\n\n"
        for i, ch_id in enumerate(channels, 1):
            try:
                chat = await client.get_chat(ch_id)
                name = chat.title or "Unknown"
                text += f"**{i}.** {name}\n🆔 `{ch_id}`\n\n"
            except:
                text += f"**{i}.** `{ch_id}` ⚠️ (Not accessible)\n\n"
        
        text += f"\n**Total:** {len(channels)} channel(s)"
        
        await message.reply_text(text)
        
        print(f"✅ Showed {len(channels)} authorized channels")
        
    except Exception as e:
        print(f"❌ Error in authlist: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)}")

# ---------------- Caption Commands ----------------
@app.on_message(filters.command(["setcaption", "sc"]) & filters.private)
async def set_caption_cmd(client, message: Message):
    """Set caption for a channel"""
    
    print(f"🔧 setcaption command received from user {message.from_user.id}")
    
    try:
        # Get channel_id from command
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ **Usage:** `/sc <channel_id> <caption>`\n\n"
                "**Example:**\n"
                "`/sc -1001234567890 <b>{filename}</b>`\n\n"
                "**Available variables:**\n"
                "`{filename}` - File name without extension\n"
                "`{filesize}` - File size (e.g., 1.23 GB)\n"
                "`{duration}` - Video duration\n"
                "`{quality}` - Video quality (e.g., 720p)\n"
                "`{season}` - Season number\n"
                "`{episode}` - Episode number"
            )
        
        channel_id = message.command[1]
        if not channel_id.startswith('-100'):
            if channel_id.startswith('-'):
                channel_id = f"-100{channel_id.lstrip('-')}"
            else:
                channel_id = f"-100{channel_id}"
        
        # Check if authorized
        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                f"❌ **Channel not authorized!**\n\n"
                f"🆔 `{channel_id}`\n\n"
                f"Use `/capauth {channel_id}` first to authorize this channel."
            )
        
        # Extract caption
        text = message.text or ""
        parts = text.split(None, 2)
        
        if len(parts) < 3:
            return await message.reply_text(
                "❌ **Please provide caption after channel_id**\n\n"
                "**Example:**\n"
                f"`/sc {channel_id} <b>{{filename}}</b>`"
            )
        
        caption = parts[2].strip()
        await save_caption(channel_id, caption)
        
        await message.reply_text(
            f"✅ **Caption Updated!**\n\n"
            f"🆔 **Channel:** `{channel_id}`\n\n"
            f"Use `/gc {channel_id}` to preview the caption."
        )
        
        print(f"✅ Caption set for channel {channel_id}")
        
    except Exception as e:
        print(f"❌ Error in setcaption: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command(["getcaption", "gc"]) & filters.private)
async def get_caption_cmd(client, message: Message):
    """Get current caption for a channel"""
    
    print(f"🔍 getcaption command received from user {message.from_user.id}")
    
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ **Usage:** `/gc <channel_id>`\n\n"
                "**Example:** `/gc -1001234567890`"
            )
        
        channel_id = message.command[1]
        if not channel_id.startswith('-100'):
            if channel_id.startswith('-'):
                channel_id = f"-100{channel_id.lstrip('-')}"
            else:
                channel_id = f"-100{channel_id}"
        
        # Check if authorized
        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                f"❌ **Channel not authorized!**\n\n"
                f"🆔 `{channel_id}`"
            )
        
        caption = await load_caption(channel_id)
        if not caption:
            return await message.reply_text(
                f"❌ **No caption set for this channel**\n\n"
                f"🆔 `{channel_id}`"
            )
        
        preview = (caption.replace("{filename}", "Example_Filename")
                         .replace("{filesize}", "1.23 GB")
                         .replace("{duration}", "1:23:45")
                         .replace("{quality}", "480p")
                         .replace("{season}", "1")
                         .replace("{episode}", "01 (123)"))
        
        await message.reply_text(
            f"📝 **Current Caption Preview**\n\n"
            f"🆔 **Channel:** `{channel_id}`\n\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{preview}",
            parse_mode=ParseMode.HTML
        )
        
        print(f"✅ Caption shown for channel {channel_id}")
        
    except Exception as e:
        print(f"❌ Error in getcaption: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)}")

@app.on_message(filters.command(["removecaption", "rc", "rmcaption"]) & filters.private)
async def remove_caption_cmd(client, message: Message):
    """Remove caption for a channel"""
    
    print(f"🗑️ removecaption command received from user {message.from_user.id}")
    
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ **Usage:** `/rc <channel_id>`\n\n"
                "**Example:** `/rc -1001234567890`"
            )
        
        channel_id = message.command[1]
        if not channel_id.startswith('-100'):
            if channel_id.startswith('-'):
                channel_id = f"-100{channel_id.lstrip('-')}"
            else:
                channel_id = f"-100{channel_id}"
        
        # Check if authorized
        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                f"❌ **Channel not authorized!**\n\n"
                f"🆔 `{channel_id}`"
            )
        
        await remove_caption(channel_id)
        
        await message.reply_text(
            f"✅ **Caption Removed!**\n\n"
            f"🆔 **Channel:** `{channel_id}`\n\n"
            f"Auto-captioning disabled for this channel."
        )
        
        print(f"✅ Caption removed for channel {channel_id}")
        
    except Exception as e:
        print(f"❌ Error in removecaption: {e}")
        await message.reply_text(f"❌ **Error:** {str(e)}")


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

# Media handler for channels
@app.on_message((filters.document | filters.video | filters.audio | filters.photo) & filters.channel)
async def handle_bulk_channel(client, message: Message):
    """Handler for media messages in authorized channels"""
    chat_id = str(message.chat.id)
    
    # Debug logging
    print(f"📥 Media received in channel (ID: {chat_id}): {message.chat.title}")
    
    # Check if channel is authorized
    if not await is_channel_authed(chat_id):
        print(f"⚠️ Channel {chat_id} not authorized - skipping")
        return
    
    caption = await load_caption(chat_id)
    if not caption:
        print(f"⚠️ No caption set for channel {chat_id}")
        return

    fname = (message.document.file_name if message.document else
             message.video.file_name if message.video else
             message.audio.file_name if message.audio else
             "Photo")
    
    print(f"📝 Processing file: {fname}")
    
    ep_num = _int_episode(fname)
    qual = _quality_val(fname)

    async with LOCK:
        bucket = bulk_bucket[chat_id]
        bucket.setdefault((ep_num, qual), []).append(message)
        if chat_id in bulk_tasks and not bulk_tasks[chat_id].done():
            bulk_tasks[chat_id].cancel()
        bulk_tasks[chat_id] = asyncio.create_task(_flush_bulk(chat_id, BULK_WAIT))

async def _flush_bulk(chat_id: str, delay: int):
    try: 
        await asyncio.sleep(delay)
    except asyncio.CancelledError: 
        return

    async with LOCK:
        bucket = bulk_bucket.pop(chat_id, {})

    if not bucket: 
        return

    caption = await load_caption(chat_id)
    if not caption: 
        return

    ordered = []
    for (ep, qual), msgs in sorted(bucket.items()):
        ordered.extend(msgs)

    print(f"🔄 Reordering {len(ordered)} messages in channel {chat_id}")

    for msg in ordered:
        filename = filesize = duration = None
        if msg.document:
            filename = msg.document.file_name
            filesize = msg.document.file_size
        elif msg.video:
            filename = msg.video.file_name or "Video"
            filesize = msg.video.file_size
            duration = msg.video.duration
        elif msg.audio:
            filename = msg.audio.file_name or "Audio"
            filesize = msg.audio.file_size
            duration = msg.audio.duration
        elif msg.photo:
            filename = "Photo"

        if not filename: 
            continue

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
            print(f"✅ Reordered: {filename}")
        except Exception as e:
            if "FLOOD_WAIT" in str(e):
                wait = int(str(e).split("wait ")[1].split()[0])
                print(f"⚠️ Flood wait {wait}s")
                await asyncio.sleep(wait)
                try: 
                    await msg.copy(int(chat_id), caption=cap, parse_mode=ParseMode.HTML)
                    await msg.delete()
                except Exception as retry_err:
                    print(f"❌ Retry failed: {retry_err}")
            else: 
                print(f"❌ Reorder failed: {e}")
        await asyncio.sleep(1)
