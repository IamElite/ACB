import html
import re
import asyncio
from collections import defaultdict
from typing import Union, Tuple, Optional

from pyrogram import filters, raw
from pyrogram.types import Message, Chat
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait
from pyrogram.file_id import FileId

from DURGESH import app
from DURGESH.database import db

captiondb = db.captions
authchanneldb = db.capauth_channels
episodetitledb = db.episode_titles

                          
DEFAULT_CAPTION = """<blockquote><b>
╭────────────────────⦿
├ 📺<b>єᴘɪꜱσᴅє</b> ➛ <i>{episode}</i> <b>(ꜱєᴧꜱση</b> <i>{season}</i><b>)</b>
├ 🔊<b>ᴧᴜᴅɪσ</b> ➛ <i>ʜɪηᴅɪ #σꜰꜰɪᴄɪᴧʟ</i>
├ 🎥<b>ǫᴜᴧʟɪᴛʏ</b> ➛ <i>{quality}</i>
├ 🌐<b>[ @TGUrlsHub & @TGEliteHub ]</b>
╰────────────────────⦿
</blockquote></b>"""

                                               
DEFAULT_STICKER = "CAACAgUAAyEFAASGx2_SAAIz62jrdgpaY3r_OHj_ffvmcjhhNnuBAAI7FQACdQGhVWIKZdj6_6puHgQ"

def extract_episode(fname: str) -> str:
    """Extract episode number from filename."""
    for pat, grp in (
        (r'EPS(\d+)\s*EP(\d+)\s*\((\d+)\)', (2, 3)),
        (r'S(\d+)\s*(?:E|EP)(\d+)\s*\((\d+)\)', (2, 3)),
        (r'S(\d+)\s*(?:E|EP)(\d+)', (2,)),
        (r'S(\d+)\s*E?P?\s*(\d+)', (2,)),
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
    """Extract season number from filename."""
    for pat in (
        r'S(\d+)(?:E|EP)(\d+)',
        r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)',
        r'S(\d+)[^\d]*(\d+)',
        r'S(\d+)\s*E?P?\s*(\d+)',
        r'\bseason\s*(\d+)\b',
        r'\bs(\d+)\b'
    ):
        m = re.search(pat, fname, re.IGNORECASE)
        if m:
            return m.group(1).zfill(2)
    return "N/A"

def extract_quality(text: str) -> str:
    """Extract video quality from filename."""
    qpats = [
        (r'[(\[{<]?\s*4k\s*[)\]}>]?', "4K"),
        (r'[(\[{<]?\s*2k\s*[)\]}>]?', "2K"),
        (r'[(\[{<]?\s*4kX264\s*[)\]}>]?', "4K X264"),
        (r'[(\[{<]?\s*4kx265\s*[)\]}>]?', "4K X265"),
        (r'[(\[{<]?\s*(\d{3,4})[pP]\s*[)\]}>]?', None),
        (r'\b(\d{3,4})[pP]\b', None),
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


def get_readable_file_size(size_in_bytes: Optional[int]) -> str:
    """Convert bytes to human-readable format."""
    if not size_in_bytes:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    idx = 0
    size = float(size_in_bytes)
    while size >= 1024 and idx < len(units) - 1:
        size /= 1024
        idx += 1
    return f"{size:.2f} {units[idx]}"


def format_duration(duration: Optional[int]) -> str:
    """Format duration in seconds to HH:MM:SS or MM:SS."""
    if not duration:
        return "N/A"
    try:
        secs = int(duration)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
    except Exception:
        return "N/A"

async def copy_media_preserving_cover(
    client,
    target_chat_id: int,
    msg: Message,
    caption: str
) -> Optional[Message]:
    try:
        copied = await msg.copy(
            target_chat_id,
            caption=caption,
            parse_mode=ParseMode.HTML
        )
    except FloodWait:
        raise
    except Exception:
        raise

    if not copied or not msg.video or not msg.video.video_cover:
        return copied

    try:
        video_file = FileId.decode(copied.video.file_id)
        cover_file = FileId.decode(msg.video.video_cover.file_id)

        media = raw.types.InputMediaDocument(
            id=raw.types.InputDocument(
                id=video_file.media_id,
                access_hash=video_file.access_hash,
                file_reference=video_file.file_reference
            ),
            video_cover=raw.types.InputPhoto(
                id=cover_file.media_id,
                access_hash=cover_file.access_hash,
                file_reference=cover_file.file_reference
            ),
            video_timestamp=msg.video.video_start_timestamp,
            ttl_seconds=msg.video.ttl_seconds,
            spoiler=bool(copied.has_media_spoiler)
        )

        peer = await client.resolve_peer(target_chat_id)
        await client.invoke(
            raw.functions.messages.EditMessage(
                peer=peer,
                id=copied.id,
                media=media
            )
        )
        return await client.get_messages(target_chat_id, copied.id)
    except FloodWait:
        raise
    except Exception as e:
        print(f"⚠️ Video cover preservation failed: {e}")
        return copied

def normalize_channel_peer(val: Union[str, int]) -> Union[int, str]:
    """
    Normalizes input into an integer channel ID or username string.
    Crucial for Kurigram: Any numeric ID MUST be an integer, otherwise
    Pyrogram / Kurigram assumes it's a phone number and calls contacts.ResolvePhone.
    """
    if isinstance(val, int):
        return val

    clean = str(val).strip()

                                                                     
    m_link = re.search(r'(?:https?://)?t\.me/c/(\d+)', clean)
    if m_link:
        return int(f"-100{m_link.group(1)}")

                                         
    m_user = re.search(r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)', clean)
    if m_user:
        return f"@{m_user.group(1)}"

                            
    if clean.startswith("@"):
        return clean

                                                               
    clean_digits = clean.lstrip('-')
    if clean_digits.isdigit():
        if clean_digits.startswith("100"):
            return int(f"-{clean_digits}")
        return int(f"-100{clean_digits}")

    return clean


async def resolve_target_channel(client, message: Message, arg_index: int = 1) -> Tuple[Optional[str], Optional[Chat]]:
    """
    Safely resolves the channel ID and Chat object from commands or replied messages.
    Bypasses contacts.ResolvePhone by utilizing message.reply_to_message objects directly.
    """
                                                            
    if message.reply_to_message:
        r = message.reply_to_message
        if r.forward_from_chat:
            return str(r.forward_from_chat.id), r.forward_from_chat
        if r.sender_chat:
            return str(r.sender_chat.id), r.sender_chat

                                                                  
    raw_target = None
    if len(message.command) > arg_index:
        raw_target = message.command[arg_index]
    elif message.reply_to_message and (message.reply_to_message.text or message.reply_to_message.caption):
        body = (message.reply_to_message.text or message.reply_to_message.caption).strip().split()
        if body:
            raw_target = body[0]

    if raw_target is None:
        return None, None

    peer = normalize_channel_peer(raw_target)
    
                                            
    chat = await client.get_chat(peer)
    return str(chat.id), chat

async def add_auth_channel(chat_id: str):
    await authchanneldb.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {"chat_id": str(chat_id)}},
        upsert=True
    )


async def remove_auth_channel(chat_id: str):
    await authchanneldb.delete_one({"chat_id": str(chat_id)})


async def is_channel_authed(chat_id: str) -> bool:
    data = await authchanneldb.find_one({"chat_id": str(chat_id)})
    return bool(data)


async def get_all_auth_channels() -> list[str]:
    cursor = authchanneldb.find({})
    return [doc["chat_id"] async for doc in cursor]


async def load_episode_titles(chat_id: str) -> dict:
    data = await episodetitledb.find_one({"chat_id": str(chat_id)})
    return data.get("titles", {}) if data else {}

async def save_episode_titles(chat_id: str, titles: dict):
    await episodetitledb.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {"chat_id": str(chat_id), "titles": {str(k): str(v) for k, v in titles.items()}}},
        upsert=True
    )

def _episode_title_number(value: str) -> Optional[int]:
    try:
        match = re.search(r"(?:episode|ep|e|eps)\s*[-._:#]?\s*(\d+)", value, re.IGNORECASE)
        if not match:
            match = re.match(r"\s*[-._\[\(]?\s*(\d{1,3})\s*[-.:)]", value)
        if not match:
            match = re.match(r"\s*(\d{1,3})\s+", value)
        return int(match.group(1)) if match else None
    except Exception:
        return None

def _parse_episode_title_text(text: str) -> dict[int, str]:
    result = {}
    if not text:
        return result

    for raw_line in re.split(r"[\r\n]+", text):
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue

        number = _episode_title_number(line)
        if number is None:
            continue

        title = re.sub(
            r"^\s*(?:episode|ep|eps|e)\s*[-._:#]?\s*\d{1,3}\s*(?:[-.:)]+\s*|\s+)",
            "",
            line,
            flags=re.IGNORECASE
        )
        if title == line:
            title = re.sub(r"^\s*\d{1,3}\s*[-.:)]\s*", "", line)
        if title == line:
            title = re.sub(r"^\s*\d{1,3}\s+", "", line)

        title = title.strip(" -:|–—")
        if title:
            result[number] = title

    return result

def _title_for_episode(episode_titles: dict, ep_num: int, fallback: str) -> str:
    title = episode_titles.get(str(ep_num)) or episode_titles.get(ep_num)
    return str(title).strip() if title else fallback

async def load_caption(chat_id: str):
    data = await captiondb.find_one({"chat_id": str(chat_id)})
    return data["caption"] if data else None


async def save_caption(
    chat_id: str,
    caption: str,
    sticker_id: Optional[str] = None,
    episode_header: Optional[bool] = None
):
    update_data = {"caption": caption}
    if sticker_id:
        update_data["sticker_id"] = sticker_id
    if episode_header is not None:
        update_data["episode_header"] = episode_header

    await captiondb.update_one(
        {"chat_id": str(chat_id)},
        {"$set": update_data},
        upsert=True
    )


async def load_sticker(chat_id: str) -> str:
    data = await captiondb.find_one({"chat_id": str(chat_id)})
    return data.get("sticker_id", DEFAULT_STICKER) if data else DEFAULT_STICKER


async def load_episode_header_setting(chat_id: str) -> bool:
    data = await captiondb.find_one({"chat_id": str(chat_id)})
    return data.get("episode_header", True) if data else True


async def remove_caption(chat_id: str):
    await captiondb.delete_one({"chat_id": str(chat_id)})

@app.on_message(filters.command(["capauth", "ca"]))
async def auth_channel_cmd(client, message: Message):
    try:
        try:
            channel_id, chat = await resolve_target_channel(client, message, arg_index=1)
        except Exception as e:
            return await message.reply_text(
                f"⚠️ <b>Error: Cannot access channel!</b>\n\n"
                f"<b>Reason:</b> {html.escape(str(e))}\n\n"
                f"<i>Make sure the bot has been added as an admin with post privileges in the channel.</i>",
                parse_mode=ParseMode.HTML
            )

        if not channel_id or not chat:
            return await message.reply_text(
                "❌ <b>Usage:</b>\n\n"
                "• <code>/ca &lt;channel_id or @username&gt;</code>\n"
                "• Or reply to a forwarded message from the channel with <code>/ca</code>\n\n"
                "<b>Example:</b> <code>/ca -1003100372976</code>",
                parse_mode=ParseMode.HTML
            )

        chat_name = chat.title or "Authorized Channel"

        await add_auth_channel(channel_id)
        await save_caption(channel_id, DEFAULT_CAPTION, DEFAULT_STICKER, True)

        await message.reply_text(
            f"✅ <b>Channel Authorized Successfully!</b>\n\n"
            f"📺 <b>Channel:</b> {html.escape(chat_name)}\n"
            f"🆔 <b>ID:</b> <code>{channel_id}</code>\n\n"
            f"⚙️ <b>Default Settings Configured:</b>\n"
            f"• Episode Header: <code>ON ✅</code>\n"
            f"• Separator Sticker: <code>Set ✅</code>\n\n"
            f"<b>Useful Commands:</b>\n"
            f"• <code>/gc {channel_id}</code> — View current settings\n"
            f"• <code>/sc {channel_id} &lt;caption&gt; -ep off</code> — Change caption & settings",
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
        try:
            channel_id, _ = await resolve_target_channel(client, message, arg_index=1)
        except Exception as e:
            return await message.reply_text(f"❌ <b>Error:</b> {html.escape(str(e))}", parse_mode=ParseMode.HTML)

        if not channel_id:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/capunauth &lt;channel_id&gt;</code>",
                parse_mode=ParseMode.HTML
            )

        await remove_auth_channel(channel_id)
        await remove_caption(channel_id)

        await message.reply_text(
            f"✅ <b>Channel Unauthorized!</b>\n\n🆔 <code>{channel_id}</code>",
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
                peer = int(ch_id) if str(ch_id).lstrip("-").isdigit() else ch_id
                chat = await client.get_chat(peer)
                name = chat.title or "Unknown"
                text += f"<b>{i}.</b> {html.escape(name)}\n🆔 <code>{ch_id}</code>\n\n"
            except Exception:
                text += f"<b>{i}.</b> <code>{ch_id}</code> ⚠️\n\n"

        text += f"<b>Total:</b> {len(channels)} channel(s)"
        await message.reply_text(text, parse_mode=ParseMode.HTML)

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["setcaption", "sc"]))
async def set_caption_cmd(client, message: Message):
    try:
        if len(message.command) < 2:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/sc &lt;channel_id&gt; &lt;caption&gt; -s &lt;sticker_id&gt; -ep on/off</code>\n\n"
                "<b>Examples:</b>\n"
                "1. <code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt;</code>\n"
                "2. <code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt; -ep off</code>\n"
                "3. <code>/sc -1001234567890 &lt;b&gt;{filename}&lt;/b&gt; -s CAACAgUA...</code>\n\n"
                "<b>Variables:</b> {filename}, {filesize}, {duration}, {quality}, {season}, {episode}",
                parse_mode=ParseMode.HTML
            )

        raw_id = message.command[1]
        peer = normalize_channel_peer(raw_id)

        if isinstance(peer, int):
            channel_id = str(peer)
        else:
            chat = await client.get_chat(peer)
            channel_id = str(chat.id)

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
                "❌ <b>Please provide caption text.</b>",
                parse_mode=ParseMode.HTML
            )

        full_text = parts[2].strip()

        sticker_match = re.search(r'(?:^|\s)-s\s+([^\s]+)', full_text)
        ep_match = re.search(r'(?:^|\s)-ep\s+(on|off)\b', full_text, re.IGNORECASE)

        sticker_id = sticker_match.group(1).strip() if sticker_match else None
        episode_header = (ep_match.group(1).lower() == "on") if ep_match else None

        cleaned_caption = full_text
        if sticker_match:
            cleaned_caption = cleaned_caption.replace(sticker_match.group(0), "")
        if ep_match:
            cleaned_caption = cleaned_caption.replace(ep_match.group(0), "")

        cleaned_caption = cleaned_caption.strip()

        await save_caption(channel_id, cleaned_caption, sticker_id, episode_header)

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

@app.on_message(filters.command(["setepisodetitle", "setepisode", "setep", "sept"]))
async def set_episode_title_cmd(client, message: Message):
    try:
        lines = (message.text or "").splitlines()
        if not lines:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/set &lt;episode list&gt; &lt;channel_id&gt;</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/set\n01 - The Beginning\n02 - New Journey\n-1001234567890</code>",
                parse_mode=ParseMode.HTML
            )

        command_line = lines[0]
        command_parts = command_line.split()
        channel_arg = command_parts[-1] if len(command_parts) > 1 else None

        channel_from_list = False
        if not channel_arg and len(lines) > 1:
            tail = lines[-1].strip().split()
            if tail:
                candidate = tail[-1]
                if re.match(r"^(?:-?100\d+|@?[A-Za-z0-9_]+|https?://t\.me/)", candidate):
                    try:
                        normalize_channel_peer(candidate)
                        channel_arg = candidate
                        channel_from_list = True
                    except Exception:
                        pass

        if not channel_arg and message.reply_to_message:
            reply_text = message.reply_to_message.text or message.reply_to_message.caption or ""
            reply_lines = reply_text.splitlines()
            if len(reply_lines) > 1:
                tail = reply_lines[-1].strip().split()
                if tail:
                    channel_arg = tail[-1]

        if not channel_arg:
            return await message.reply_text(
                "❌ <b>Channel ID is required at the end.</b>\n\n"
                "Use <code>/sept</code> followed by the episode list and put the channel ID at the end.",
                parse_mode=ParseMode.HTML
            )

        try:
            peer = normalize_channel_peer(channel_arg)
            chat = await client.get_chat(peer)
            channel_id = str(chat.id)
        except Exception as e:
            return await message.reply_text(
                f"❌ <b>Invalid channel:</b> {html.escape(str(e))}",
                parse_mode=ParseMode.HTML
            )

        first_line_parts = command_line.split(None, 1)
        inline_text = ""
        if len(first_line_parts) == 2:
            inline_text = re.sub(r"\s+" + re.escape(channel_arg) + r"\s*$", "", first_line_parts[1], count=1).strip()
        list_lines = lines[1:]
        if channel_from_list and list_lines:
            last_line = list_lines[-1]
            if last_line.strip() == channel_arg:
                list_lines = list_lines[:-1]
            else:
                list_lines[-1] = re.sub(r"\s+" + re.escape(channel_arg) + r"\s*$", "", last_line, count=1).strip()
        supplied_text = "\n".join([inline_text, *list_lines]).strip()
        if not supplied_text and message.reply_to_message:
            supplied_text = message.reply_to_message.text or message.reply_to_message.caption or ""

        if not supplied_text:
            return await message.reply_text(
                "❌ <b>Episode title list not found.</b>\n\n"
                "Example: <code>01 - Pilot</code> or <code>Episode 01: Pilot</code>",
                parse_mode=ParseMode.HTML
            )

        parsed = _parse_episode_title_text(supplied_text)
        if not parsed:
            return await message.reply_text(
                "❌ <b>No episode titles detected.</b>\n\n"
                "Supported format:\n"
                "<code>01 - Title</code>\n"
                "<code>Episode 02: Title</code>\n"
                "<code>EP03 - Title</code>",
                parse_mode=ParseMode.HTML
            )

        current = await load_episode_titles(channel_id)
        current.update({str(k): v for k, v in parsed.items()})
        await save_episode_titles(channel_id, current)

        preview = "\n".join(
            f"<b>{ep:02d}.</b> {html.escape(title)}"
            for ep, title in sorted(parsed.items())[:30]
        )
        extra = "" if len(parsed) <= 30 else f"\n… and {len(parsed) - 30} more"

        await message.reply_text(
            "✅ <b>Episode Titles Updated!</b>\n\n"
            f"📺 <b>Channel:</b> <code>{channel_id}</code>\n"
            f"📌 <b>Updated:</b> <code>{len(parsed)}</code>\n\n"
            f"{preview}{extra}",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.command(["getcaption", "gc"]))
async def get_caption_cmd(client, message: Message):
    try:
        try:
            channel_id, _ = await resolve_target_channel(client, message, arg_index=1)
        except Exception as e:
            return await message.reply_text(f"❌ <b>Error:</b> {html.escape(str(e))}", parse_mode=ParseMode.HTML)

        if not channel_id:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/gc &lt;channel_id&gt;</code>",
                parse_mode=ParseMode.HTML
            )

        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                f"❌ <b>Channel not authorized!</b>\n\n"
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
            .replace("{episode}", "The Beginning")
            .replace("{episode_no}", "01 (123)")
            .replace("{episode_title}", "The Beginning")
        )

        response = (
            "📝 <b>Current Settings</b>\n\n"
            f"🆔 <code>{channel_id}</code>\n"
            f"📺 Episode Header: {'ON ✅' if episode_header else 'OFF ❌'}\n\n"
            "━━━━━━━━━━━━━━━━\n"
            f"{preview}"
        )

        await message.reply_text(response, parse_mode=ParseMode.HTML)

        if sticker_id:
            try:
                await message.reply_sticker(sticker_id)
            except Exception:
                pass

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )


@app.on_message(filters.command(["getsticker", "gs"]))
async def get_sticker_cmd(client, message: Message):
    try:
        try:
            channel_id, _ = await resolve_target_channel(client, message, arg_index=1)
        except Exception as e:
            return await message.reply_text(f"❌ <b>Error:</b> {html.escape(str(e))}", parse_mode=ParseMode.HTML)

        if not channel_id:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/gs &lt;channel_id&gt;</code>",
                parse_mode=ParseMode.HTML
            )

        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                f"❌ <b>Channel not authorized!</b>\n\n"
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
        try:
            channel_id, _ = await resolve_target_channel(client, message, arg_index=1)
        except Exception as e:
            return await message.reply_text(f"❌ <b>Error:</b> {html.escape(str(e))}", parse_mode=ParseMode.HTML)

        if not channel_id:
            return await message.reply_text(
                "❌ <b>Usage:</b> <code>/rc &lt;channel_id&gt;</code>",
                parse_mode=ParseMode.HTML
            )

        if not await is_channel_authed(channel_id):
            return await message.reply_text(
                f"❌ <b>Channel not authorized!</b>\n\n"
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
    except Exception:
        pass
    return 9999

def _message_filename(msg: Message) -> str:
    if msg.document:
        return msg.document.file_name or "Document"
    if msg.video:
        return msg.video.file_name or "Video"
    if msg.audio:
        return msg.audio.file_name or "Audio"
    return ""

def _collect_message_episode_titles(messages: list[Message]) -> dict[int, str]:
    titles = {}
    ordered = sorted((m for m in messages if m), key=lambda m: m.id)
    media = [m for m in ordered if m.document or m.video or m.audio]
    media_by_id = {m.id: m for m in media}

    for item in ordered:
        if item.document or item.video or item.audio or item.photo:
            continue
        text = item.text or item.caption or ""
        if not text:
            continue

        parsed = _parse_episode_title_text(text)
        if parsed:
            titles.update(parsed)
            continue

        reply_id = getattr(item, "reply_to_message_id", None)
        if reply_id in media_by_id:
            ep_num = _int_episode(_message_filename(media_by_id[reply_id]))
            clean = re.sub(r"\\s+", " ", text).strip()
            if ep_num != 9999 and clean:
                titles[ep_num] = clean
                continue

        prev_media = next((m for m in reversed(media) if m.id < item.id), None)
        next_media = next((m for m in media if m.id > item.id), None)
        if prev_media and next_media and next_media.id - prev_media.id > 1:
            continue
        candidate = prev_media or next_media
        if candidate:
            ep_num = _int_episode(_message_filename(candidate))
            clean = re.sub(r"\\s+", " ", text).strip()
            if ep_num != 9999 and clean and len(clean) <= 300:
                titles[ep_num] = clean

    return titles

def _caption_values(filename: str, filesize, duration, episode_titles: dict) -> dict:
    episode_no = extract_episode(filename)
    ep_num = _int_episode(filename)
    return {
        "filename": html.escape(filename.rsplit(".", 1)[0]),
        "filesize": html.escape(get_readable_file_size(filesize)),
        "duration": html.escape(format_duration(duration)),
        "quality": html.escape(extract_quality(filename)),
        "season": html.escape(extract_season(filename)),
        "episode": html.escape(_title_for_episode(episode_titles, ep_num, episode_no)),
        "episode_no": html.escape(episode_no),
        "episode_title": html.escape(_title_for_episode(episode_titles, ep_num, "")),
    }

def _render_caption(template: str, values: dict) -> str:
    result = template
    for key, value in values.items():
        result = result.replace("{" + key + "}", value)
    return result

@app.on_message(
    (filters.document | filters.video | filters.text) &
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

    source_titles = _collect_message_episode_titles(messages)
    stored_titles = await load_episode_titles(chat_id)
    episode_titles = dict(stored_titles)
    episode_titles.update({str(k): v for k, v in source_titles.items()})

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

    sorted_episodes = sorted(episodes.items())
    int_chat_id = int(chat_id)

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
                    int_chat_id,
                    f"<b>━━━ Episode {ep_num:02d} ━━━</b>",
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(1)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                print(f"❌ Header error: {e}")

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

            cap = _render_caption(
                caption_template,
                _caption_values(filename, filesize, duration, episode_titles)
            )

            try:
                await copy_media_preserving_cover(client, int_chat_id, msg, cap)
                await asyncio.sleep(0.5)

                await msg.delete()
                await asyncio.sleep(0.5)

            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                try:
                    copied = await copy_media_preserving_cover(
                        client, int_chat_id, msg, cap
                    )
                    if copied:
                        await msg.delete()
                except Exception as retry_error:
                    print(f"❌ Copy retry error: {retry_error}")
            except Exception as e:
                print(f"❌ Copy error: {e}")

        if ep_num != 9999:
            try:
                await client.send_sticker(int_chat_id, sticker_id)
                await asyncio.sleep(1)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                print(f"❌ Sticker error: {e}")

@app.on_message(filters.private & filters.command(["autocap", "ac"]))
async def auto_cap_cmd(client, message: Message):
    try:
        if len(message.command) != 4:
            return await message.reply_text(
                "❌ <b>Usage:</b>\n"
                "• <code>/ac &lt;start_link&gt; &lt;end_link&gt; &lt;channel_id&gt;</code>\n\n"
                "👉 <b>Example:</b>\n"
                "<code>/ac https://t.me/c/2906536289/1824 "
                "https://t.me/c/2906536289/1995 -1002572090742</code>",
                parse_mode=ParseMode.HTML
            )

        start_arg = message.command[1]
        end_arg = message.command[2]
        dest_arg = message.command[3]

        def parse_link(arg: str):
            m = re.search(r'(?:https?://)?t\.me/c/(\d+)/(\d+)', arg)
            if not m:
                return None, None
            return m.group(1), int(m.group(2))

        src1_internal, start_id = parse_link(start_arg)
        src2_internal, end_id = parse_link(end_arg)

        if not (src1_internal and src2_internal and start_id and end_id):
            return await message.reply_text(
                "❌ <b>Please provide valid <code>t.me/c/...</code> links for both start and end.</b>",
                parse_mode=ParseMode.HTML
            )

        if src1_internal != src2_internal:
            return await message.reply_text(
                "❌ <b>Start and end links must be from the same channel!</b>",
                parse_mode=ParseMode.HTML
            )

        from_channel = int(f"-100{src1_internal}")
        dest_peer = normalize_channel_peer(dest_arg)

        try:
            dest_chat = await client.get_chat(dest_peer)
            real_dest_id = str(dest_chat.id)
            dest_int_id = dest_chat.id
        except Exception as e:
            return await message.reply_text(
                f"⚠️ <b>Cannot access destination channel:</b> {html.escape(str(e))}\n\n"
                f"Make sure bot is an admin in the destination channel.",
                parse_mode=ParseMode.HTML
            )

        if start_id > end_id:
            start_id, end_id = end_id, start_id

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
                f"Use <code>/sc {real_dest_id} &lt;caption&gt;</code> first.",
                parse_mode=ParseMode.HTML
            )

        sticker_id = await load_sticker(real_dest_id)
        episode_header_enabled = await load_episode_header_setting(real_dest_id)

        try:
            await client.get_chat(from_channel)
        except Exception as e:
            return await message.reply_text(
                f"⚠️ <b>Cannot access source channel:</b> {html.escape(str(e))}\n\n"
                f"Make sure the bot is a member/admin in the source channel.",
                parse_mode=ParseMode.HTML
            )

        await message.reply_text(
            "✅ <b>Starting auto caption…</b>\n\n"
            f"📦 <b>From:</b> <code>{from_channel}</code>\n"
            f"📤 <b>To:</b> <code>{real_dest_id}</code>\n"
            f"📩 <b>Range:</b> <code>{start_id}</code> ➝ <code>{end_id}</code>",
            parse_mode=ParseMode.HTML
        )

        msg_ids = list(range(start_id, end_id + 1))
        CHUNK = 200

        for i in range(0, len(msg_ids), CHUNK):
            chunk_ids = msg_ids[i:i + CHUNK]

            try:
                msgs = await client.get_messages(from_channel, chunk_ids)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                msgs = await client.get_messages(from_channel, chunk_ids)
            except Exception as e:
                await message.reply_text(
                    f"⚠️ <b>Error fetching messages:</b> <code>{html.escape(str(e))}</code>",
                    parse_mode=ParseMode.HTML
                )
                continue

            source_titles = _collect_message_episode_titles(msgs)
            stored_titles = await load_episode_titles(real_dest_id)
            episode_titles = dict(stored_titles)
            episode_titles.update({str(k): v for k, v in source_titles.items()})

            episodes = defaultdict(list)

            for msg in msgs:
                if not msg:
                    continue

                if not (msg.document or msg.video):
                    continue

                fname = msg.document.file_name if msg.document else (msg.video.file_name or "Video")
                ep_num = _int_episode(fname)
                episodes[ep_num].append(msg)

            sorted_episodes = sorted(episodes.items())

            for ep_num, msgs_in_episode in sorted_episodes:
                sorted_msgs = sorted(
                    msgs_in_episode,
                    key=lambda m: _quality_val(
                        m.document.file_name if m.document else
                        m.video.file_name if m.video else "Video"
                    )
                )

                if episode_header_enabled and ep_num != 9999:
                    try:
                        await client.send_message(
                            dest_int_id,
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

                    if not filename:
                        continue

                    cap = _render_caption(
                        caption_template,
                        _caption_values(filename, filesize, duration, episode_titles)
                    )

                    try:
                        await copy_media_preserving_cover(client, dest_int_id, msg, cap)
                        await asyncio.sleep(0.5)
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                        try:
                            await copy_media_preserving_cover(
                                client, dest_int_id, msg, cap
                            )
                        except Exception as e:
                            print(f"❌ Copy retry error (ac): {e}")
                    except Exception as e:
                        print(f"❌ Copy error (ac): {e}")

                if ep_num != 9999:
                    try:
                        await client.send_sticker(dest_int_id, sticker_id)
                        await asyncio.sleep(1)
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value)
                    except Exception as e:
                        print(f"❌ Sticker error (ac): {e}")

        await message.reply_text(
            "✅ <b>Auto caption completed for given range!</b>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )
