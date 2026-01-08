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
        (r'S(\d+)\s*E?P?\s*(\d+)', (2,)),  # Added: S01 E05 or S01 EP05
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
    for pat in (
        r'S(\d+)(?:E|EP)(\d+)',
        r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)',
        r'S(\d+)[^\d]*(\d+)',
        r'S(\d+)\s*E?P?\s*(\d+)',  # Added: S01 E05 or S01 EP05
        r'\bseason\s*(\d+)\b',
        r'\bs(\d+)\b'
    ):
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
        (r'[(\[{<]?\s*(\d{3,4})[pP]\s*[)\]}>]?', None),  # Modified: handles brackets
        (r'\b(\d{3,4})[pP]\b', None),  # Added: plain 480p, 720p, 1080p
        (r'\bWEB[.\- ]*DL\b', "WEB-DL"),
        (r'[(\[{<]?\s*HdRip\s*[)\]}>]?|\bHdRip\b', "HDRip"),
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

# ---------------- Caption & Sticker Database ----------------
async def load_caption(chat_id: str):
    data = await captiondb.find_one({"chat_id": chat_id})
    return data["caption"] if data else None

async def save_caption(
    chat_id: str,
    caption: str,
    sticker_id: str = None,
    episode_header: bool = None
):
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

async def load_sticker(chat_id: str):
    data = await captiondb.find_one({"chat_id": chat_id})
    return data.get("sticker_id", DEFAULT_STICKER) if data else DEFAULT_STICKER

async def load_episode_header_setting(chat_id: str) -> bool:
    data = await captiondb.find_one({"chat_id": chat_id})
    return data.get("episode_header", True) if data else True

async def remove_caption(chat_id: str):
    await captiondb.delete_one({"chat_id": chat_id})

# ---------------- Auth Commands ----------------
@app.on_message(filters.command(["capauth", "ca"]))
async def auth_channel_cmd(client, message: Message):
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
                "❌ <b>Usage:</b>\n\n"
                "<code>/capauth &lt;channel_id&gt;</code> or <code>/ca &lt;channel_id&gt;</code>\n\n"
                "<b>Example:</b> <code>/ca -1001234567890</code>",
                parse_mode=ParseMode.HTML
            )

        try:
            chat = await client.get_chat(channel_id)
            chat_name = chat.title or "Unknown"
        except Exception as e:
            return await message.reply_text(
                f"⚠️ <b>Error:</b> Cannot access channel!\n\n"
                f"<b>Channel ID:</b> <code>{channel_id}</code>\n\n"
                f"<b>Reason:</b> {html.escape(str(e))}\n\n"
                f"Make sure bot is admin in the channel.",
                parse_mode=ParseMode.HTML
            )

        await add_auth_channel(channel_id)
        await save_caption(channel_id, DEFAULT_CAPTION, DEFAULT_STICKER, True)

        await message.reply_text(
            f"✅ <b>Channel Authorized!</b>\n\n"
            f"📺 <b>Channel:</b> {html.escape(chat_name)}\n"
            f"🆔 <b>ID:</b> <code>{channel_id}</code>\n\n"
            f"✅ Default settings applied\n"
            f"• Episode Header: ON ✅\n\n"
            f"<b>Commands:</b>\n"
            f"• <code>/gc {channel_id}</code> - View settings\n"
            f"• <code>/sc {channel_id} &lt;caption&gt; -ep off</code> - Disable headers",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["capunauth", "cua"]))
async def unauth_channel_cmd(client, message: Message):
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
                "❌ <b>Usage:</b> <code>/capunauth &lt;channel_id&gt;</code>",
                parse_mode=ParseMode.HTML
            )

        await remove_auth_channel(channel_id)
        await remove_caption(channel_id)

        await message.reply_text(
            f"✅ <b>Channel Unauthorized!</b>\n\n"
            f"🆔 <code>{channel_id}</code>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["capauthlist", "cal"]))
async def list_auth_channels_cmd(client, message: Message):
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
                text += f"<b>{i}.</b> <code>{ch_id}</code> ⚠️\n\n"

        text += f"<b>Total:</b> {len(channels)} channel(s)"
        await message.reply_text(text, parse_mode=ParseMode.HTML)

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )

# ---------------- Caption Commands ----------------
@app.on_message(filters.command(["setcaption", "sc"]))
async def set_caption_cmd(client, message: Message):
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/sc &lt;channel_id&gt; &lt;caption&gt; -s &lt;sticker_id&gt; -ep on/off</code>\n\n"
                "<b>Examples:</b>\n"
                "1. <code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt;</code>\n"
                "2. <code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt; -ep off</code>\n"
                "3. <code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt; -s CAACAgUA...</code>\n"
                "4. <code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt; -s CAACAgUA... -ep off</code>\n\n"
                "<b>Variables:</b> {filename}, {filesize}, {duration}, {quality}, {season}, {episode}",
                parse_mode=ParseMode.HTML
            )

        channel_id = message.command[1]
        if not channel_id.startswith('-100'):
            if channel_id.startswith('-'):
                channel_id = f"-100{channel_id.lstrip('-')}"
            else:
                channel_id = f"-100{channel_id}"

        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                f"❌ <b>Channel not authorized!</b>\n\n"
                f"Use <code>/capauth {channel_id}</code> first.",
                parse_mode=ParseMode.HTML
            )

        text = message.text or ""
        parts = text.split(None, 2)

        if len(parts) < 3:
            return await message.reply_text(
                "❌ <b>Please provide caption</b>",
                parse_mode=ParseMode.HTML
            )

        full_text = parts[2].strip()
        sticker_id = None
        episode_header = None
        caption = full_text

        # Parse -s flag
        if " -s " in full_text:
            split_parts = full_text.split(" -s ", 1)
            caption = split_parts[0].strip()
            remaining = split_parts[1].strip()

            if " -ep " in remaining:
                ep_split = remaining.split(" -ep ", 1)
                sticker_id = ep_split[0].strip()
                ep_value = ep_split[1].strip().lower()
                episode_header = ep_value == "on"
            else:
                sticker_id = remaining

        # Parse -ep flag (without -s)
        elif " -ep " in full_text:
            split_parts = full_text.split(" -ep ", 1)
            caption = split_parts[0].strip()
            ep_value = split_parts[1].strip().lower()
            episode_header = ep_value == "on"

        await save_caption(channel_id, caption, sticker_id, episode_header)

        response = f"✅ <b>Settings Updated!</b>\n\n🆔 <code>{channel_id}</code>\n\n"

        if sticker_id:
            response += "🎨 Custom sticker set\n"
        if episode_header is not None:
            response += f"📺 Episode Header: {'ON' if episode_header else 'OFF'}\n"

        response += f"\n<code>/gc {channel_id}</code> to preview"

        await message.reply_text(response, parse_mode=ParseMode.HTML)

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["getcaption", "gc"]))
async def get_caption_cmd(client, message: Message):
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/gc &lt;channel_id&gt;</code>",
                parse_mode=ParseMode.HTML
            )

        channel_id = message.command[1]
        if not channel_id.startswith('-100'):
            if channel_id.startswith('-'):
                channel_id = f"-100{channel_id.lstrip('-')}"
            else:
                channel_id = f"-100{channel_id}"

        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                "❌ <b>Channel not authorized!</b>\n\n"
                f"Use <code>/capauth {channel_id}</code> first.",
                parse_mode=ParseMode.HTML
            )

        caption = await load_caption(channel_id)
        if not caption:
            return await message.reply_text(
                "❌ <b>No caption set</b>",
                parse_mode=ParseMode.HTML
            )

        sticker_id = await load_sticker(channel_id)
        episode_header = await load_episode_header_setting(channel_id)

        preview = (
            caption
            .replace("{filename}", "Example_Filename")
            .replace("{filesize}", "1.23 GB")
            .replace("{duration}", "1:23:45")
            .replace("{quality}", "480p")
            .replace("{season}", "01")
            .replace("{episode}", "01 (123)")
        )

        response = (
            "📝 <b>Current Settings</b>\n\n"
            f"🆔 <code>{channel_id}</code>\n"
            f"📺 Episode Header: {'ON ✅' if episode_header else 'OFF ❌'}\n\n"
            "━━━━━━━━━━━━━━━━\n"
            f"{preview}"
        )

        await message.reply_text(response, parse_mode=ParseMode.HTML)

        try:
            await message.reply_sticker(sticker_id)
        except:
            pass

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["getsticker", "gs"]))
async def get_sticker_cmd(client, message: Message):
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/gs &lt;channel_id&gt;</code>",
                parse_mode=ParseMode.HTML
            )

        channel_id = message.command[1]
        if not channel_id.startswith('-100'):
            if channel_id.startswith('-'):
                channel_id = f"-100{channel_id.lstrip('-')}"
            else:
                channel_id = f"-100{channel_id}"

        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                "❌ <b>Channel not authorized!</b>\n\n"
                f"Use <code>/capauth {channel_id}</code> first.",
                parse_mode=ParseMode.HTML
            )

        sticker_id = await load_sticker(channel_id)

        await message.reply_text(
            "🎨 <b>Current Sticker</b>\n\n"
            f"🆔 <code>{channel_id}</code>\n"
            f"🎨 <code>{sticker_id}</code>",
            parse_mode=ParseMode.HTML
        )

        try:
            await message.reply_sticker(sticker_id)
        except Exception as e:
            await message.reply_text(f"⚠️ {html.escape(str(e))}")

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["removecaption", "rc", "rmcaption"]))
async def remove_caption_cmd(client, message: Message):
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/rc &lt;channel_id&gt;</code>",
                parse_mode=ParseMode.HTML
            )

        channel_id = message.command[1]
        if not channel_id.startswith('-100'):
            if channel_id.startswith('-'):
                channel_id = f"-100{channel_id.lstrip('-')}"
            else:
                channel_id = f"-100{channel_id}"

        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                "❌ <b>Channel not authorized!</b>\n\n"
                f"Use <code>/capauth {channel_id}</code> first.",
                parse_mode=ParseMode.HTML
            )

        await remove_caption(channel_id)

        await message.reply_text(
            "✅ <b>Caption Removed!</b>\n\n"
            f"🆔 <code>{channel_id}</code>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )

# ---------------- Bulk Handler (channel uploads) ----------------
bulk_bucket: dict[str, list[Message]] = defaultdict(list)
bulk_tasks: dict[str, asyncio.Task] = {}
BULK_WAIT = 3
LOCK = asyncio.Lock()

def _quality_val(fname: str) -> int:
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
    try:
        raw = extract_episode(fname)
        match = re.search(r'(\d+)', raw)
        if match:
            return int(match.group(1))
    except:
        pass
    return 9999

@app.on_message(
    (filters.document | filters.video) &
    filters.channel,
    group=10
)
async def handle_bulk_channel(client, message: Message):
    try:
        chat_id = str(message.chat.id)

        if not await is_channel_authed(chat_id):
            return

        caption_template = await load_caption(chat_id)
        if not caption_template:
            return

        async with LOCK:
            bulk_bucket[chat_id].append(message)

            if chat_id in bulk_tasks and not bulk_tasks[chat_id].done():
                bulk_tasks[chat_id].cancel()

            bulk_tasks[chat_id] = asyncio.create_task(
                _flush_bulk(client, chat_id, BULK_WAIT)
            )

    except Exception as e:
        print(f"❌ Handler error: {e}")

async def _flush_bulk(client, chat_id: str, delay: int):
    try:
        await asyncio.sleep(delay)
    except asyncio.CancelledError:
        return

    async with LOCK:
        messages = bulk_bucket.pop(chat_id, [])

    if not messages:
        return

    caption_template = await load_caption(chat_id)
    sticker_id = await load_sticker(chat_id)
    episode_header_enabled = await load_episode_header_setting(chat_id)

    if not caption_template:
        return

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

    # Sort episodes
    sorted_episodes = sorted(episodes.items())

    for ep_num, msgs_in_episode in sorted_episodes:
        # Sort by quality within episode
        sorted_msgs = sorted(
            msgs_in_episode,
            key=lambda m: _quality_val(
                m.document.file_name if m.document else
                m.video.file_name if m.video else
                m.audio.file_name if m.audio else "Photo"
            )
        )

        # Send episode header at START (if enabled and valid episode)
        if episode_header_enabled and ep_num != 9999:
            try:
                await client.send_message(
                    int(chat_id),
                    f"<b>━━━ Episode {ep_num:02d} ━━━</b>",
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(1)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                print(f"❌ Header error: {e}")

        # Process all files
        for msg in sorted_msgs:
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

            cap = (
                caption_template
                .replace("{filename}", html.escape(filename.rsplit('.', 1)[0]))
                .replace("{filesize}", html.escape(get_readable_file_size(filesize)))
                .replace("{duration}", html.escape(format_duration(duration)))
                .replace("{quality}", html.escape(extract_quality(filename)))
                .replace("{season}", html.escape(extract_season(filename)))
                .replace("{episode}", html.escape(extract_episode(filename)))
            )

            try:
                await msg.copy(
                    int(chat_id),
                    caption=cap,
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(0.5)

                await msg.delete()
                await asyncio.sleep(0.5)

            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                try:
                    await msg.copy(
                        int(chat_id),
                        caption=cap,
                        parse_mode=ParseMode.HTML
                    )
                    await msg.delete()
                except:
                    pass
            except Exception as e:
                print(f"❌ Copy error: {e}")

        # Send sticker separator at END (always send if valid episode)
        if ep_num != 9999:
            try:
                await client.send_sticker(int(chat_id), sticker_id)
                await asyncio.sleep(1)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                print(f"❌ Sticker error: {e}")

# ---------------- /ac Command (use-channel -> capauth channel) ----------------
@app.on_message(filters.private & filters.command(["autocap", "ac"]))
async def auto_cap_cmd(client, message: Message):
    try:
        # /ac <start> <end> <dest_channel>
        if len(message.command) != 4:
            return await message.reply_text(
                "❌ <b>Usage:</b>\n"
                "• <code>/ac &lt;start_link&gt; &lt;end_link&gt; &lt;channel_id&gt;</code>\n"
                "• <code>/ac &lt;start_msg_id&gt; &lt;end_msg_id&gt; &lt;channel_id&gt;</code>\n\n"
                "👉 <b>Example:</b>\n"
                "<code>/ac https://t.me/c/2906536289/1824 "
                "https://t.me/c/2906536289/1995 -1002572090742</code>",
                parse_mode=ParseMode.HTML
            )

        start_arg = message.command[1]
        end_arg = message.command[2]
        dest_arg = message.command[3]

        # ---------- Helpers ----------
        def parse_link(arg: str):
            # Return (internal_id, msg_id) from t.me/c link, else (None, None)
            m = re.search(r'(?:https?://)?t\.me/c/(\d+)/(\d+)', arg)
            if not m:
                return None, None
            return m.group(1), int(m.group(2))

        def parse_msg_id(arg: str) -> int:
            # If link -> msg_id, else plain int
            _, mid = parse_link(arg)
            if mid is not None:
                return mid
            return int(arg)

        # ---------- Source channel + msg ids from start/end ----------
        src1_internal, start_from_link = parse_link(start_arg)
        src2_internal, end_from_link = parse_link(end_arg)

        if src1_internal or src2_internal:
            # Expect both links & same /c/ id
            if not (src1_internal and src2_internal):
                return await message.reply_text(
                    "❌ <b>Start aur end dono ko same type me do.</b>\n"
                    "Dono <code>t.me/c/...</code> links hone chahiye.",
                    parse_mode=ParseMode.HTML
                )
            if src1_internal != src2_internal:
                return await message.reply_text(
                    "❌ <b>Start aur end links alag channels ke hain.</b>\n"
                    "Dono links same source channel se lo.",
                    parse_mode=ParseMode.HTML
                )

            from_channel = f"-100{src1_internal}"
            start_id = start_from_link
            end_id = end_from_link
        else:
            # Dono plain IDs diye gaye (no link).
            # Yaha hum source channel nahi guess kar sakte, to error dekar clear bol dete.
            return await message.reply_text(
                "❌ <b>Source detect nahi ho raha.</b>\n"
                "Please <b>start</b> & <b>end</b> ke liye <code>t.me/c/.../msg_id</code> links use karo.\n\n"
                "Example:\n"
                "<code>/ac https://t.me/c/2906536289/1824 "
                "https://t.me/c/2906536289/1995 -1002572090742</code>",
                parse_mode=ParseMode.HTML
            )

        # ---------- Destination channel ----------
        # yaha par sirf id ya @username allow kar rahe hain, t.me link nahi
        if "t.me/" in dest_arg:
            return await message.reply_text(
                "❌ <b>Destination ke liye t.me link mat do.</b>\n"
                "Yaha <code>-100...</code> ya <code>@ChannelUsername</code> use karo.\n\n"
                "Example:\n"
                "<code>/ac https://t.me/c/2906536289/1824 "
                "https://t.me/c/2906536289/1995 -1002572090742</code>",
                parse_mode=ParseMode.HTML
            )

        # dest can be @username OR numeric id
        if dest_arg.startswith("@"):
            # username: Pyrogram will resolve
            dest_ref = dest_arg
            chat = await client.get_chat(dest_ref)
            real_dest_id = str(chat.id)
        else:
            # numeric-like: normalize to -100...
            to_channel = dest_arg
            if not to_channel.startswith("-100"):
                if to_channel.startswith("-"):
                    to_channel = f"-100{to_channel.lstrip('-')}"
                else:
                    to_channel = f"-100{to_channel}"
            dest_ref = int(to_channel)
            real_dest_id = to_channel

        # Normalize range
        if start_id > end_id:
            start_id, end_id = end_id, start_id

        # ---------- Check capauth on destination ----------
        if not await is_channel_authed(real_dest_id):
            return await message.reply_text(
                f"❌ <b>Destination channel not authorized!</b>\n\n"
                f"Use <code>/capauth {real_dest_id}</code> first.",
                parse_mode=ParseMode.HTML
            )

        caption_template = await load_caption(real_dest_id)
        if not caption_template:
            return await message.reply_text(
                "❌ <b>No caption set for this destination channel.</b>\n"
                "Use <code>/sc &lt;channel_id&gt; &lt;caption&gt;</code> first.",
                parse_mode=ParseMode.HTML
            )

        sticker_id = await load_sticker(real_dest_id)
        episode_header_enabled = await load_episode_header_setting(real_dest_id)

        # ---------- Access check: source + destination ----------
        try:
            await client.get_chat(int(from_channel))
        except Exception as e:
            return await message.reply_text(
                "⚠️ <b>Cannot access source channel.</b>\n\n"
                f"<b>Source:</b> <code>{from_channel}</code>\n"
                f"<b>Reason:</b> <code>{html.escape(str(e))}</code>\n\n"
                "Make sure bot is member/admin in <b>source</b> channel.",
                parse_mode=ParseMode.HTML
            )

        try:
            await client.get_chat(dest_ref)
        except Exception as e:
            return await message.reply_text(
                "⚠️ <b>Cannot access destination channel.</b>\n\n"
                f"<b>Destination:</b> <code>{real_dest_id}</code>\n"
                f"<b>Reason:</b> <code>{html.escape(str(e))}</code>\n\n"
                "Make sure bot is admin in <b>destination</b> channel.",
                parse_mode=ParseMode.HTML
            )

        await message.reply_text(
            "✅ <b>Starting auto caption…</b>\n\n"
            f"📦 <b>From:</b> <code>{from_channel}</code>\n"
            f"📤 <b>To:</b> <code>{real_dest_id}</code>\n"
            f"📩 <b>Range:</b> <code>{start_id}</code> ➝ <code>{end_id}</code>",
            parse_mode=ParseMode.HTML
        )

        # ---------- Main processing ----------
        msg_ids = list(range(start_id, end_id + 1))
        CHUNK = 200

        for i in range(0, len(msg_ids), CHUNK):
            chunk_ids = msg_ids[i:i + CHUNK]

            try:
                msgs = await client.get_messages(int(from_channel), chunk_ids)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                msgs = await client.get_messages(int(from_channel), chunk_ids)
            except Exception as e:
                await message.reply_text(
                    "⚠️ <b>Error while fetching messages:</b> "
                    f"<code>{html.escape(str(e))}</code>",
                    parse_mode=ParseMode.HTML
                )
                continue

            episodes = defaultdict(list)

            for msg in msgs:
                if not msg:
                    continue

                if not (msg.document or msg.video):
                    continue

                if msg.document:
                    fname = msg.document.file_name
                elif msg.video:
                    fname = msg.video.file_name or "Video"
                elif msg.audio:
                    fname = msg.audio.file_name or "Audio"
                else:
                    fname = "Photo"

                ep_num = _int_episode(fname)
                episodes[ep_num].append(msg)

            sorted_episodes = sorted(episodes.items())

            for ep_num, msgs_in_episode in sorted_episodes:
                sorted_msgs = sorted(
                    msgs_in_episode,
                    key=lambda m: _quality_val(
                        m.document.file_name if m.document else
                        m.video.file_name if m.video else
                        m.audio.file_name if m.audio else "Photo"
                    )
                )

                if episode_header_enabled and ep_num != 9999:
                    try:
                        await client.send_message(
                            dest_ref if isinstance(dest_ref, int) else int(real_dest_id),
                            f"<b>━━━ Episode {ep_num:02d} ━━━</b>",
                            parse_mode=ParseMode.HTML
                        )
                        await asyncio.sleep(1)
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                    except Exception as e:
                        print(f"❌ Header error (ac): {e}")

                for msg in sorted_msgs:
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

                    cap = (
                        caption_template
                        .replace("{filename}", html.escape(filename.rsplit(".", 1)[0]))
                        .replace("{filesize}", html.escape(get_readable_file_size(filesize)))
                        .replace("{duration}", html.escape(format_duration(duration)))
                        .replace("{quality}", html.escape(extract_quality(filename)))
                        .replace("{season}", html.escape(extract_season(filename)))
                        .replace("{episode}", html.escape(extract_episode(filename)))
                    )

                    try:
                        await msg.copy(
                            dest_ref if isinstance(dest_ref, int) else int(real_dest_id),
                            caption=cap,
                            parse_mode=ParseMode.HTML
                        )
                        await asyncio.sleep(0.5)
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                        try:
                            await msg.copy(
                                dest_ref if isinstance(dest_ref, int) else int(real_dest_id),
                                caption=cap,
                                parse_mode=ParseMode.HTML
                            )
                        except Exception as e:
                            print(f"❌ Copy retry error (ac): {e}")
                    except Exception as e:
                        print(f"❌ Copy error (ac): {e}")

                if ep_num != 9999:
                    try:
                        await client.send_sticker(
                            dest_ref if isinstance(dest_ref, int) else int(real_dest_id),
                            sticker_id
                        )
                        await asyncio.sleep(1)
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                    except Exception as e:
                        print(f"❌ Sticker error (ac): {e}")

        await message.reply_text(
            "✅ <b>Auto caption completed for given range.</b>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )
