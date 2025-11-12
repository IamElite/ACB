import html
import re
import asyncio
from collections import defaultdict
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from DURGESH import app
from DURGESH.database import db

captiondb = db.captions
authchanneldb = db.capauth_channels

# Default caption
DEFAULT_CAPTION = """<blockquote>
╭────────────────────⦿
├ 📺<b>єᴘɪꜱσᴅє</b> ➛ <i>{episode}</i> <b>(ꜱєᴧꜱση</b> <i>{season}</i><b>)</b>
├ 🔊<b>ᴧᴜᴅɪσ</b> ➛ <i>ʜɪηᴅɪ #σꜰꜰɪᴄɪᴧʟ</i>
├ 🎥<b>ǫᴜᴧʟɪᴛʏ</b> ➛ <i>{quality}</i>
├ 🌐<b>[ @TGUrlsHub & @TGEliteHub ]</b>
╰────────────────────⦿
</blockquote>"""

# Default sticker file_id for episode separator
DEFAULT_STICKER = "CAACAgUAAyEFAASGx2_SAAIz62jrdgpaY3r_OHj_ffvmcjhhNnuBAAI7FQACdQGhVWIKZdj6_6puHgQ"

# ---------------- Helpers ----------------
def extract_episode(fname: str) -> str:
    """Extract episode number from filename"""
    for pat, grp in (
        (r'EPS(\d+)\s*EP(\d+)\s*\((\d+)\)', (2, 3)),
        (r'S(\d+)\s*(?:E|EP)(\d+)\s*\((\d+)\)', (2, 3)),
        (r'S(\d+)\s*(?:E|EP)(\d+)', (2,)),
        (r'(?:E|EP)\s*\((\d+)\)', (1,)),
        (r'(?:E|EP)(\d+)', (1,)),
        (r'-\s*(\d+)', (1,))
    ):
        m = re.search(pat, fname, re.IGNORECASE)
        if m:
            if len(grp) == 2:
                return f"{m.group(grp[0]).zfill(2)} ({m.group(grp[1])})"
            return f"{m.group(grp[0]).zfill(2)}"
    return "N/A"

def extract_season(fname: str) -> str:
    """Extract season number from filename"""
    for pat in (r'S(\d+)(?:E|EP)(\d+)', r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)',
                r'S(\d+)[^\d]*(\d+)', r'\bseason\s*(\d+)\b', r'\bs(\d+)\b'):
        m = re.search(pat, fname, re.IGNORECASE)
        if m:
            return m.group(1).zfill(2)
    return "N/A"

def extract_quality(text: str) -> str:
    """Extract quality from filename"""
    qpats = [
        (r'[(\[{<]?\s*4k\s*[)\]}>]?', "4K"),
        (r'[(\[{<]?\s*2k\s*[)\]}>]?', "2K"),
        (r'[(\[{<]?\s*4kX264\s*[)\]}>]?', "4K X264"),
        (r'[(\[{<]?\s*4kx265\s*[)\]}>]?', "4K X265"),
        (r'\bWEB[.\- ]*DL\b', "WEB-DL"),
        (r'[(\[{<]?\s*HdRip\s*[)\]}>]?|\bHdRip\b', "HDRip"),
        (r'(\d{3,4})[pP]', None),
    ]
    for pat, repl in qpats:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            q = repl if repl else m.group(1) + "p"
            if q and "360" in q.lower():
                return "480p"
            return q
    return "N/A"

def get_readable_file_size(size_in_bytes) -> str:
    """Convert bytes to readable format"""
    if not size_in_bytes:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    size = float(size_in_bytes)
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.2f} {units[idx]}"

def format_duration(duration) -> str:
    """Format duration in HH:MM:SS"""
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
    """Add channel to authorized list"""
    await authchanneldb.update_one(
        {"chat_id": chat_id},
        {"$set": {"chat_id": chat_id}},
        upsert=True
    )
    print(f"✅ Database: Channel {chat_id} added to auth list")

async def remove_auth_channel(chat_id: str):
    """Remove channel from authorized list"""
    await authchanneldb.delete_one({"chat_id": chat_id})
    print(f"✅ Database: Channel {chat_id} removed from auth list")

async def is_channel_authed(chat_id: str) -> bool:
    """Check if channel is authorized"""
    data = await authchanneldb.find_one({"chat_id": chat_id})
    result = bool(data)
    print(f"🔍 Database: Channel {chat_id} auth check = {result}")
    return result

async def get_all_auth_channels():
    """Get all authorized channels"""
    cursor = authchanneldb.find({})
    channels = [doc["chat_id"] async for doc in cursor]
    print(f"📋 Database: Found {len(channels)} authorized channels")
    return channels

# ---------------- Caption & Sticker Database ----------------
async def load_caption(chat_id: str):
    """Load caption for a channel"""
    data = await captiondb.find_one({"chat_id": chat_id})
    caption = data["caption"] if data else None
    print(f"📝 Database: Caption for {chat_id} = {'Found' if caption else 'Not found'}")
    return caption

async def save_caption(chat_id: str, caption: str, sticker_id: str = None, episode_header: bool = None):
    """Save caption, sticker, and episode header setting for a channel"""
    update_data = {"caption": caption}
    if sticker_id:
        update_data["sticker_id"] = sticker_id
    if episode_header is not None:
        update_data["episode_header"] = episode_header
    
    await captiondb.update_one(
        {"chat_id": chat_id}, 
        {"$set": update_data}, 
        upsert=True
    )
    print(f"✅ Database: Caption saved for {chat_id} (ep_header: {episode_header})")

async def load_sticker(chat_id: str):
    """Load sticker for a channel"""
    data = await captiondb.find_one({"chat_id": chat_id})
    sticker = data.get("sticker_id", DEFAULT_STICKER) if data else DEFAULT_STICKER
    print(f"🎨 Database: Sticker for {chat_id} = {sticker[:20]}...")
    return sticker

async def load_episode_header_setting(chat_id: str) -> bool:
    """Load episode header setting for a channel (default: True)"""
    data = await captiondb.find_one({"chat_id": chat_id})
    enabled = data.get("episode_header", True) if data else True
    print(f"📺 Database: Episode header for {chat_id} = {enabled}")
    return enabled

async def remove_caption(chat_id: str):
    """Remove caption for a channel"""
    await captiondb.delete_one({"chat_id": chat_id})
    print(f"✅ Database: Caption removed for {chat_id}")

# ---------------- Auth Commands ----------------
@app.on_message(filters.command(["capauth", "ca"]))
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
                "❌ <b>Usage:</b>\n\n"
                "<code>/capauth &lt;channel_id&gt;</code>\n"
                "or\n"
                "<code>/ca &lt;channel_id&gt;</code>\n\n"
                "<b>Example:</b> <code>/ca -1001234567890</code>\n\n"
                "Or reply to a forwarded channel message with <code>/ca</code>",
                parse_mode=ParseMode.HTML
            )
        
        # Try to get chat info to verify
        try:
            chat = await client.get_chat(channel_id)
            chat_name = chat.title or "Unknown"
            print(f"✅ Channel found: {chat_name} ({channel_id})")
        except Exception as e:
            print(f"❌ Error accessing channel: {e}")
            return await message.reply_text(
                f"⚠️ <b>Error:</b> Cannot access channel!\n\n"
                f"<b>Channel ID:</b> <code>{channel_id}</code>\n\n"
                f"<b>Reason:</b> {html.escape(str(e))}\n\n"
                f"<b>Solution:</b>\n"
                f"1. Make sure bot is added as admin in the channel\n"
                f"2. Bot needs 'Post Messages' and 'Delete Messages' permissions\n"
                f"3. Check if channel ID is correct",
                parse_mode=ParseMode.HTML
            )
        
        # Add to auth list
        await add_auth_channel(channel_id)
        
        # Set default caption, sticker, and episode header (ON by default)
        await save_caption(channel_id, DEFAULT_CAPTION, DEFAULT_STICKER, True)
        
        await message.reply_text(
            f"✅ <b>Channel Authorized!</b>\n\n"
            f"📺 <b>Channel:</b> {html.escape(chat_name)}\n"
            f"🆔 <b>ID:</b> <code>{channel_id}</code>\n\n"
            f"✅ Default settings applied:\n"
            f"• Caption: Set ✅\n"
            f"• Sticker: Set ✅\n"
            f"• Episode Header: ON ✅\n\n"
            f"<b>Next Steps:</b>\n"
            f"• Upload media to channel to test\n"
            f"• Use <code>/gc {channel_id}</code> to view caption\n"
            f"• Use <code>/sc {channel_id} &lt;caption&gt; -ep off</code> to disable episode headers",
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        print(f"❌ Unexpected error in capauth: {e}")
        await message.reply_text(
            f"❌ <b>Unexpected Error:</b> {html.escape(str(e))}", 
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["capunauth", "cua"]))
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
                "❌ <b>Usage:</b> <code>/capunauth &lt;channel_id&gt;</code> or <code>/cua &lt;channel_id&gt;</code>\n\n"
                "<b>Example:</b> <code>/cua -1001234567890</code>",
                parse_mode=ParseMode.HTML
            )
        
        await remove_auth_channel(channel_id)
        await remove_caption(channel_id)
        
        await message.reply_text(
            f"✅ <b>Channel Unauthorized!</b>\n\n"
            f"🆔 <b>ID:</b> <code>{channel_id}</code>\n\n"
            f"Caption removed and auto-captioning disabled.",
            parse_mode=ParseMode.HTML
        )
        
        print(f"✅ Channel {channel_id} unauthorized")
        
    except Exception as e:
        print(f"❌ Error in capunauth: {e}")
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}", 
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["capauthlist", "cal"]))
async def list_auth_channels_cmd(client, message: Message):
    """List all authorized channels"""
    print(f"📋 authlist command received from user {message.from_user.id}")
    
    try:
        channels = await get_all_auth_channels()
        
        if not channels:
            return await message.reply_text(
                "⚠️ <b>No channels authorized yet.</b>\n\n"
                "Use <code>/capauth &lt;channel_id&gt;</code> to authorize a channel.",
                parse_mode=ParseMode.HTML
            )
        
        text = "✅ <b>Authorized Channels:</b>\n\n"
        for i, ch_id in enumerate(channels, 1):
            try:
                chat = await client.get_chat(ch_id)
                name = chat.title or "Unknown"
                text += f"<b>{i}.</b> {html.escape(name)}\n🆔 <code>{ch_id}</code>\n\n"
            except:
                text += f"<b>{i}.</b> <code>{ch_id}</code> ⚠️ (Not accessible)\n\n"
        
        text += f"\n<b>Total:</b> {len(channels)} channel(s)"
        
        await message.reply_text(text, parse_mode=ParseMode.HTML)
        
        print(f"✅ Showed {len(channels)} authorized channels")
        
    except Exception as e:
        print(f"❌ Error in authlist: {e}")
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}", 
            parse_mode=ParseMode.HTML
        )

# ---------------- Caption Commands ----------------
@app.on_message(filters.command(["setcaption", "sc"]))
async def set_caption_cmd(client, message: Message):
    """Set caption, sticker, and episode header setting for a channel"""
    print(f"🔧 setcaption command received from user {message.from_user.id}")
    
    try:
        # Get channel_id from command
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/sc &lt;channel_id&gt; &lt;caption&gt; -s &lt;sticker_id&gt; -ep on/off</code>\n\n"
                "<b>Examples:</b>\n"
                "1. Caption only:\n"
                "<code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt;</code>\n\n"
                "2. Caption + disable episode header:\n"
                "<code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt; -ep off</code>\n\n"
                "3. Caption + sticker:\n"
                "<code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt; -s CAACAgUA...</code>\n\n"
                "4. Caption + sticker + disable episode header:\n"
                "<code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt; -s CAACAgUA... -ep off</code>\n\n"
                "<b>Available variables:</b>\n"
                "<code>{filename}</code> - File name without extension\n"
                "<code>{filesize}</code> - File size (e.g., 1.23 GB)\n"
                "<code>{duration}</code> - Video duration\n"
                "<code>{quality}</code> - Video quality (e.g., 720p)\n"
                "<code>{season}</code> - Season number\n"
                "<code>{episode}</code> - Episode number\n\n"
                "<b>Tip:</b> To get sticker ID, forward any sticker to @RawDataBot",
                parse_mode=ParseMode.HTML
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
                f"❌ <b>Channel not authorized!</b>\n\n"
                f"🆔 <code>{channel_id}</code>\n\n"
                f"Use <code>/capauth {channel_id}</code> first to authorize this channel.",
                parse_mode=ParseMode.HTML
            )
        
        # Extract caption, sticker, and episode header setting
        text = message.text or ""
        parts = text.split(None, 2)
        
        if len(parts) < 3:
            return await message.reply_text(
                "❌ <b>Please provide caption after channel_id</b>\n\n"
                "<b>Example:</b>\n"
                f"<code>/sc {channel_id} &lt;b&gt;{{filename}}&lt;/b&gt;</code>",
                parse_mode=ParseMode.HTML
            )
        
        full_text = parts[2].strip()
        
        # Parse flags
        sticker_id = None
        episode_header = None
        caption = full_text
        
        # Check for -s flag (sticker)
        if " -s " in full_text:
            split_parts = full_text.split(" -s ", 1)
            caption = split_parts[0].strip()
            remaining = split_parts[1].strip()
            
            # Check if there's -ep flag after -s
            if " -ep " in remaining:
                ep_split = remaining.split(" -ep ", 1)
                sticker_id = ep_split[0].strip()
                ep_value = ep_split[1].strip().lower()
                episode_header = ep_value == "on"
            else:
                sticker_id = remaining
            
            print(f"📌 Sticker ID provided: {sticker_id}")
        
        # Check for -ep flag (without -s)
        elif " -ep " in full_text:
            split_parts = full_text.split(" -ep ", 1)
            caption = split_parts[0].strip()
            ep_value = split_parts[1].strip().lower()
            episode_header = ep_value == "on"
        
        if episode_header is not None:
            print(f"📺 Episode header set to: {'ON' if episode_header else 'OFF'}")
        
        # Save caption, sticker, and episode header setting
        await save_caption(channel_id, caption, sticker_id, episode_header)
        
        response = f"✅ <b>Settings Updated!</b>\n\n" \
                   f"🆔 <b>Channel:</b> <code>{channel_id}</code>\n\n"
        
        if sticker_id:
            response += f"🎨 <b>Sticker:</b> Custom sticker set!\n"
        
        if episode_header is not None:
            response += f"📺 <b>Episode Header:</b> {'ON ✅' if episode_header else 'OFF ❌'}\n"
        
        response += f"\nUse <code>/gc {channel_id}</code> to preview."
        
        await message.reply_text(response, parse_mode=ParseMode.HTML)
        
        print(f"✅ Settings updated for channel {channel_id}")
        
    except Exception as e:
        print(f"❌ Error in setcaption: {e}")
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}", 
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["getcaption", "gc"]))
async def get_caption_cmd(client, message: Message):
    """Get current caption and settings for a channel"""
    print(f"🔍 getcaption command received from user {message.from_user.id}")
    
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/gc &lt;channel_id&gt;</code>\n\n"
                "<b>Example:</b> <code>/gc -1001234567890</code>",
                parse_mode=ParseMode.HTML
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
                f"❌ <b>Channel not authorized!</b>\n\n"
                f"🆔 <code>{channel_id}</code>",
                parse_mode=ParseMode.HTML
            )
        
        caption = await load_caption(channel_id)
        if not caption:
            return await message.reply_text(
                f"❌ <b>No caption set for this channel</b>\n\n"
                f"🆔 <code>{channel_id}</code>",
                parse_mode=ParseMode.HTML
            )
        
        sticker_id = await load_sticker(channel_id)
        episode_header = await load_episode_header_setting(channel_id)
        
        preview = (caption
                   .replace("{filename}", "Example_Filename")
                   .replace("{filesize}", "1.23 GB")
                   .replace("{duration}", "1:23:45")
                   .replace("{quality}", "480p")
                   .replace("{season}", "01")
                   .replace("{episode}", "01 (123)"))
        
        response = f"📝 <b>Current Settings</b>\n\n" \
                   f"🆔 <b>Channel:</b> <code>{channel_id}</code>\n" \
                   f"📺 <b>Episode Header:</b> {'ON ✅' if episode_header else 'OFF ❌'}\n" \
                   f"🎨 <b>Sticker ID:</b> <code>{sticker_id}</code>\n\n" \
                   f"━━━━━━━━━━━━━━━━━━\n" \
                   f"<b>Caption Preview:</b>\n\n" \
                   f"{preview}"
        
        await message.reply_text(response, parse_mode=ParseMode.HTML)
        
        # Send sticker preview
        try:
            await message.reply_sticker(sticker_id)
        except Exception as e:
            print(f"⚠️ Could not send sticker preview: {e}")
        
        print(f"✅ Settings shown for channel {channel_id}")
        
    except Exception as e:
        print(f"❌ Error in getcaption: {e}")
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}", 
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["getsticker", "gs"]))
async def get_sticker_cmd(client, message: Message):
    """Get current sticker for a channel"""
    print(f"🎨 getsticker command received from user {message.from_user.id}")
    
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/gs &lt;channel_id&gt;</code>\n\n"
                "<b>Example:</b> <code>/gs -1001234567890</code>",
                parse_mode=ParseMode.HTML
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
                f"❌ <b>Channel not authorized!</b>\n\n"
                f"🆔 <code>{channel_id}</code>",
                parse_mode=ParseMode.HTML
            )
        
        sticker_id = await load_sticker(channel_id)
        
        await message.reply_text(
            f"🎨 <b>Current Sticker</b>\n\n"
            f"🆔 <b>Channel:</b> <code>{channel_id}</code>\n"
            f"🎨 <b>Sticker ID:</b> <code>{sticker_id}</code>",
            parse_mode=ParseMode.HTML
        )
        
        # Send sticker
        try:
            await message.reply_sticker(sticker_id)
        except Exception as e:
            await message.reply_text(f"⚠️ Could not send sticker: {html.escape(str(e))}")
        
        print(f"✅ Sticker shown for channel {channel_id}")
        
    except Exception as e:
        print(f"❌ Error in getsticker: {e}")
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}", 
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["removecaption", "rc", "rmcaption"]))
async def remove_caption_cmd(client, message: Message):
    """Remove caption for a channel"""
    print(f"🗑️ removecaption command received from user {message.from_user.id}")
    
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ <b>Usage:</b> odede>/rc &lt;channel_id&gt;</code>\n\n"
                "<b>Example:</b> <code>/rc -1001234567890</code>",
                parse_mode=ParseMode.HTML
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
                f"❌ <b>Channel not authorized!</b>\n\n"
                f"🆔 <code>{channel_id}</code>",
                parse_mode=ParseMode.HTML
            )
        
        await remove_caption(channel_id)
        
        await message.reply_text(
            f"✅ <b>Caption Removed!</b>\n\n"
            f"🆔 <b>Channel:</b> <code>{channel_id}</code>\n\n"
            f"Auto-captioning disabled for this channel.",
            parse_mode=ParseMode.HTML
        )
        
        print(f"✅ Caption removed for channel {channel_id}")
        
    except Exception as e:
        print(f"❌ Error in removecaption: {e}")
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}", 
            parse_mode=ParseMode.HTML
        )

# ---------------- Bulk Handler ----------------
bulk_bucket: dict[str, list[Message]] = defaultdict(list)
bulk_tasks: dict[str, asyncio.Task] = {}
BULK_WAIT = 3  # 3 seconds wait time
LOCK = asyncio.Lock()

def _quality_val(fname: str) -> int:
    """Get numeric quality value for sorting"""
    txt = fname.upper()
    if "360" in txt or "360P" in txt:
        return 360
    if "480" in txt or "480P" in txt:
        return 480
    if "720" in txt or "720P" in txt:
        return 720
    if "1080" in txt or "1080P" in txt or "FHD" in txt:
        return 1080
    if "4K" in txt or "2160" in txt or "2160P" in txt:
        return 2160
    return 9999

def _int_episode(fname: str) -> int:
    """Extract episode number as integer for sorting"""
    try:
        raw = extract_episode(fname)
        # Extract first number found
        match = re.search(r'(\d+)', raw)
        if match:
            return int(match.group(1))
    except:
        pass
    return 9999

# Media handler for channels
@app.on_message(
    (filters.document | filters.video | filters.audio | filters.photo) & 
    filters.channel,
    group=10
)
async def handle_bulk_channel(client, message: Message):
    """Handler for media messages in authorized channels"""
    try:
        chat_id = str(message.chat.id)
        
        # Debug logging
        print(f"\n{'='*50}")
        print(f"📥 MEDIA RECEIVED")
        print(f"Channel: {message.chat.title}")
        print(f"Channel ID: {chat_id}")
        print(f"Message ID: {message.id}")
        
        # Get filename for logging
        fname = "Unknown"
        if message.document:
            fname = message.document.file_name
        elif message.video:
            fname = message.video.file_name or "Video"
        elif message.audio:
            fname = message.audio.file_name or "Audio"
        elif message.photo:
            fname = "Photo"
        
        print(f"File: {fname}")
        
        # Check if channel is authorized
        is_authed = await is_channel_authed(chat_id)
        if not is_authed:
            print(f"⚠️ Channel {chat_id} NOT authorized - skipping")
            print(f"{'='*50}\n")
            return
        
        print(f"✅ Channel IS authorized")
        
        # Check caption
        caption_template = await load_caption(chat_id)
        if not caption_template:
            print(f"⚠️ No caption template set for {chat_id}")
            print(f"{'='*50}\n")
            return
        
        print(f"✅ Caption template found")
        print(f"✅ Adding to bulk bucket...")
        
        async with LOCK:
            bulk_bucket[chat_id].append(message)
            print(f"📦 Bucket size: {len(bulk_bucket[chat_id])} message(s)")
            
            # Cancel existing task and create new one
            if chat_id in bulk_tasks and not bulk_tasks[chat_id].done():
                print(f"⏳ Cancelling previous flush task")
                bulk_tasks[chat_id].cancel()
            
            print(f"⏱️ Starting new flush task (wait: {BULK_WAIT}s)")
            bulk_tasks[chat_id] = asyncio.create_task(
                _flush_bulk(client, chat_id, BULK_WAIT)
            )
        
        print(f"{'='*50}\n")
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in handle_bulk_channel: {e}")
        import traceback
        traceback.print_exc()

async def _flush_bulk(client, chat_id: str, delay: int):
    """Process and reorder bulk messages"""
    try:
        print(f"\n🔄 Flush task started for {chat_id}, waiting {delay}s...")
        await asyncio.sleep(delay)
        print(f"✅ Wait completed, processing now...")
    except asyncio.CancelledError:
        print(f"⚠️ Flush task cancelled for {chat_id}")
        return

    async with LOCK:
        messages = bulk_bucket.pop(chat_id, [])

    if not messages:
        print(f"⚠️ No messages to process for {chat_id}")
        return

    caption_template = await load_caption(chat_id)
    sticker_id = await load_sticker(chat_id)
    episode_header_enabled = await load_episode_header_setting(chat_id)
    
    if not caption_template:
        print(f"⚠️ No caption template for {chat_id}")
        return

    print(f"\n{'='*50}")
    print(f"🔄 BULK PROCESSING STARTED")
    print(f"Channel: {chat_id}")
    print(f"Messages: {len(messages)}")
    print(f"Episode Header: {'ON' if episode_header_enabled else 'OFF'}")
    print(f"{'='*50}\n")

    # Group by episode
    episodes = defaultdict(list)
    for msg in messages:
        fname = None
        if msg.document:
            fname = msg.document.file_name
        elif msg.video:
            fname = msg.video.file_name or "Video"
        elif msg.audio:
            fname = msg.audio.file_name or "Audio"
        elif msg.photo:
            fname = "Photo"
        
        if fname:
            ep_num = _int_episode(fname)
            episodes[ep_num].append(msg)
            print(f"📁 File: {fname} → Episode {ep_num}")

    # Sort episodes
    sorted_episodes = sorted(episodes.items())
    print(f"\n📊 Found {len(sorted_episodes)} episode(s)\n")

    for ep_num, msgs_in_episode in sorted_episodes:
        print(f"\n{'─'*50}")
        print(f"📺 Processing Episode {ep_num} ({len(msgs_in_episode)} file(s))")
        print(f"{'─'*50}")
        
        # Sort by quality within episode (lowest to highest)
        sorted_msgs = sorted(msgs_in_episode, key=lambda m: _quality_val(
            m.document.file_name if m.document else
            m.video.file_name if m.video else
            m.audio.file_name if m.audio else "Photo"
        ))

        # Send episode header only if enabled AND valid episode number
        if episode_header_enabled and ep_num != 9999:
            try:
                await client.send_message(
                    int(chat_id),
                    f"<b>━━━ Episode {ep_num:02d} ━━━</b>",
                    parse_mode=ParseMode.HTML
                )
                print(f"✅ Sent episode header: Episode {ep_num:02d}")
                await asyncio.sleep(1)
            except FloodWait as fw:
                print(f"⚠️ FloodWait {fw.value}s on episode header")
                await asyncio.sleep(fw.value)
            except Exception as e:
                print(f"❌ Failed to send episode header: {e}")
        elif not episode_header_enabled:
            print(f"⏭️ Episode header DISABLED - skipping")

        # Process all qualities for this episode
        for idx, msg in enumerate(sorted_msgs, 1):
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

            print(f"  {idx}. Processing: {filename}")

            # Format caption
            cap = (caption_template
                   .replace("{filename}", html.escape(filename.rsplit('.', 1)[0]))
                   .replace("{filesize}", html.escape(get_readable_file_size(filesize)))
                   .replace("{duration}", html.escape(format_duration(duration)))
                   .replace("{quality}", html.escape(extract_quality(filename)))
                   .replace("{season}", html.escape(extract_season(filename)))
                   .replace("{episode}", html.escape(extract_episode(filename))))

            try:
                # Copy message with new caption
                await msg.copy(
                    int(chat_id), 
                    caption=cap, 
                    parse_mode=ParseMode.HTML
                )
                print(f"     ✅ Copied with new caption")
                await asyncio.sleep(0.5)
                
                # Delete original message
                await msg.delete()
                print(f"     ✅ Deleted original")
                await asyncio.sleep(0.5)
                
            except FloodWait as fw:
                print(f"     ⚠️ FloodWait {fw.value}s")
                await asyncio.sleep(fw.value)
                try:
                    await msg.copy(
                        int(chat_id), 
                        caption=cap, 
                        parse_mode=ParseMode.HTML
                    )
                    await msg.delete()
                    print(f"     ✅ Retry successful")
                except Exception as retry_err:
                    print(f"     ❌ Retry failed: {retry_err}")
            except Exception as e:
                print(f"     ❌ Failed: {e}")

        # Send sticker separator after all qualities of this episode (only if episode header was sent)
        if episode_header_enabled and ep_num != 9999:
            try:
                await client.send_sticker(
                    int(chat_id),
                    sticker_id
                )
                print(f"✅ Sent separator sticker")
                await asyncio.sleep(1)
            except FloodWait as fw:
                print(f"⚠️ FloodWait {fw.value}s for sticker")
                await asyncio.sleep(fw.value)
            except Exception as e:
                print(f"❌ Failed to send sticker: {e}")

