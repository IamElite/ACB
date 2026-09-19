import html
import re
import os
import asyncio
from collections import defaultdict
from typing import Union, Tuple, Optional

from pyrogram import filters, raw
from pyrogram.file_id import FileId
from pyrogram.types import Message, Chat
from pyrogram.enums import ParseMode
from pyrogram.errors import FloodWait

from DURGESH import app
from DURGESH.database import db

captiondb = db.captions
authchanneldb = db.capauth_channels
episodetitledb = db.episode_titles

# Default caption template
DEFAULT_CAPTION = """<blockquote><b>
╭────────────────────⦿
├ 📺<b>єᴘɪꜱσᴅє</b> ➛ <i>{episode}</i> <b>(ꜱєᴧꜱση</b> <i>{season}</i><b>)</b>
├ 🔊<b>ᴧᴜᴅɪσ</b> ➛ <i>ʜɪηᴅɪ #σꜰꜰɪᴄɪᴧʟ</i>
├ 🎥<b>ǫᴜᴧʟɪᴛʏ</b> ➛ <i>{quality}</i>
├ 🌐<b>[ @TGUrlsHub & @TGEliteHub ]</b>
╰────────────────────⦿
</blockquote></b>"""

# Default sticker file_id for episode separator
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
) -> Message:
    """Copy cached media and preserve Telegram video cover through the monkey-patched send methods."""
    if msg.video and getattr(msg.video, "video_cover", None):
        cover_file_id = msg.video.video_cover.file_id

        try:
            sent = await client.send_cached_media(
                chat_id=target_chat_id,
                file_id=msg.video.file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                has_spoiler=bool(getattr(msg, "has_media_spoiler", False)),
                cover=cover_file_id,
            )
            if sent:
                return sent
        except TypeError:
            pass
        except Exception as e:
            print(f"Cached video cover send failed: {e}")

        try:
            sent = await client.send_video(
                chat_id=target_chat_id,
                video=msg.video.file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                duration=msg.video.duration or 0,
                width=msg.video.width or 0,
                height=msg.video.height or 0,
                supports_streaming=True,
                has_spoiler=bool(getattr(msg, "has_media_spoiler", False)),
                cover=cover_file_id,
                file_name=msg.video.file_name or "video.mp4",
            )
            if sent:
                return sent
        except TypeError:
            pass
        except Exception as e:
            print(f"Video cover send fallback failed: {e}")

    return await msg.copy(
        target_chat_id,
        caption=caption,
        parse_mode=ParseMode.HTML
    )


def normalize_channel_peer(val: Union[str, int]) -> Union[int, str]:
    """
    Normalizes input into an integer channel ID or username string.
    Crucial for Kurigram: Any numeric ID MUST be an integer, otherwise
    Pyrogram / Kurigram assumes it's a phone number and calls contacts.ResolvePhone.
    """
    if isinstance(val, int):
        return val

    clean = str(val).strip()

    # Link format: t.me/c/2906536289 or https://t.me/c/2906536289/123
    m_link = re.search(r'(?:https?://)?t\.me/c/(\d+)', clean)
    if m_link:
        return int(f"-100{m_link.group(1)}")

    # Public username link: t.me/username
    m_user = re.search(r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)', clean)
    if m_user:
        return f"@{m_user.group(1)}"

    # Public username string
    if clean.startswith("@"):
        return clean

    # Clean leading dashes and ensure -100 prefix as an integer
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
    # Check if replied to a forwarded message from a channel
    if message.reply_to_message:
        r = message.reply_to_message
        if r.forward_from_chat:
            return str(r.forward_from_chat.id), r.forward_from_chat
        if r.sender_chat:
            return str(r.sender_chat.id), r.sender_chat

    # Extract target argument from message command or replied text
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
    
    # Resolve chat using the normalized peer
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

TITLE_LINE_RE = re.compile(
    r"^\s*(?:(?P<kind>OVA|OAV|SP|SPECIAL)\s+)?S(?P<season>\d+)\s*E(?P<episode>\d+)\s*[-:|]\s*(?P<title>.+?)\s*$",
    re.IGNORECASE
)


def parse_episode_title_lines(text: str) -> dict[str, str]:
    """Parse raw episode title lines into SxxExx keys."""
    result = {}
    if not text:
        return result

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        match = TITLE_LINE_RE.match(line)
        if not match:
            continue

        kind = (match.group("kind") or "").upper()
        season = int(match.group("season"))
        episode = int(match.group("episode"))
        title = match.group("title").strip()
        key = f"S{season:02d}E{episode:02d}"
        if kind:
            key = f"{kind}_{key}"
        result[key] = title

    return result


def media_filename(message: Message) -> Optional[str]:
    if message.document:
        return message.document.file_name
    if message.video:
        return message.video.file_name or "Video"
    if message.audio:
        return message.audio.file_name or "Audio"
    return None


def episode_key_from_filename(fname: str) -> Optional[str]:
    if not fname:
        return None

    patterns = (
        r"\bS(\d+)\s*E(\d+)\b",
        r"\bS(\d+)\s*EP(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, fname, re.IGNORECASE)
        if match:
            return f"S{int(match.group(1)):02d}E{int(match.group(2)):02d}"
    return None


def title_keys_for_filename(fname: str) -> list[str]:
    base = episode_key_from_filename(fname)
    if not base:
        return []

    upper = fname.upper()
    keys = []
    if re.search(r"\b(?:OVA|OAV)\b", upper):
        keys.append(f"OVA_{base}")
        keys.append(f"OAV_{base}")
    if re.search(r"\b(?:SP|SPECIAL)\b", upper):
        keys.append(f"SP_{base}")
        keys.append(f"SPECIAL_{base}")
    keys.append(base)
    return keys


def title_for_filename(fname: str, title_map: dict[str, str]) -> Optional[str]:
    for key in title_keys_for_filename(fname):
        if key in title_map:
            return title_map[key]
    return None


def display_title_for_key(key: str, title: str) -> str:
    """Build the separate episode title message without putting it in the video caption."""
    match = re.match(r"^(?:(OVA|OAV|SP|SPECIAL)_)?S(\d+)E(\d+)$", key, re.IGNORECASE)
    if not match:
        return title.strip()

    kind = (match.group(1) or "").upper()
    episode = int(match.group(3))
    if kind:
        return f"{kind} Episode {episode} – {title.strip()}"
    return f"Episode {episode} – {title.strip()}"


def format_episode_title_message(title: str, fname: Optional[str] = None) -> str:
    return title.strip()


async def save_episode_titles(chat_id: str, title_map: dict[str, str]):
    if not title_map:
        return
    operations = []
    for key, title in title_map.items():
        operations.append({
            "chat_id": str(chat_id),
            "key": key,
            "title": title,
        })
    for item in operations:
        await episodetitledb.update_one(
            {"chat_id": item["chat_id"], "key": item["key"]},
            {"$set": {"title": item["title"]}},
            upsert=True
        )


async def load_episode_titles(chat_id: str) -> dict[str, str]:
    result = {}
    cursor = episodetitledb.find({"chat_id": str(chat_id)})
    async for doc in cursor:
        key = doc.get("key")
        title = doc.get("title")
        if key and title:
            result[str(key)] = str(title)
    return result


async def find_existing_episode_title_message(client, chat_id: int, video_message: Message, max_back: int = 12):
    """Find an existing episode title/header message above a video."""
    if not video_message or not video_message.id:
        return None

    start_id = video_message.id - 1
    if start_id <= 0:
        return None

    ids = list(range(max(1, start_id - max_back + 1), start_id + 1))
    try:
        previous = await client.get_messages(chat_id, ids)
    except Exception:
        return None

    previous = sorted((m for m in previous if m), key=lambda m: m.id, reverse=True)
    fname = media_filename(video_message) or ""
    ep_match = re.search(r'\bS(\d+)\s*(?:E|EP)(\d+)\b', fname, re.IGNORECASE)
    episode_number = int(ep_match.group(2)) if ep_match else None

    header_candidates = []
    title_candidates = []

    for msg in previous:
        text = (msg.text or "").strip()
        if not text:
            continue

        header_match = re.match(r'^\s*━━+\s*Episode\s+(\d+)\s*━━+\s*$', text, re.IGNORECASE)
        if header_match:
            if episode_number is None or int(header_match.group(1)) == episode_number:
                header_candidates.append(msg)
            continue

        episode_match = re.search(
            r'\b(?:OVA|OAV|SP|SPECIAL)?\s*Episode\s+(\d+)\s*[–—:-]',
            text,
            re.IGNORECASE
        )
        if episode_match:
            if episode_number is None or int(episode_match.group(1)) == episode_number:
                title_candidates.append(msg)

    if title_candidates:
        return title_candidates[0]
    if header_candidates:
        return header_candidates[0]
    return None


async def replace_existing_episode_title(client, chat_id: int, video_message: Message, title: str):
    """Replace the existing title message so Telegram does not show an edited marker."""
    title_message = await find_existing_episode_title_message(client, chat_id, video_message)
    if not title_message:
        return False

    try:
        old_text = (title_message.text or title_message.caption or title.strip()).strip()
        replacement_title = title.strip()
        episode_line = re.compile(
            r'(?im)^(\s*(?:OVA|OAV|SP|SPECIAL)?\s*Episode\s+\d+\s*[–—:-].*)$'
        )
        if episode_line.search(old_text):
            new_plain = episode_line.sub(replacement_title, old_text, count=1)
        elif re.match(r'^\s*━━+\s*Episode\s+\d+\s*━━+\s*$', old_text, re.IGNORECASE):
            new_plain = replacement_title
        else:
            new_plain = replacement_title
        new_text = f"<b>{html.escape(new_plain)}</b>"

        await client.delete_messages(chat_id, title_message.id)
        await client.send_message(
            chat_id=chat_id,
            text=new_text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return True
    except Exception:
        return False


async def apply_title_to_captionless_output(client, chat_id: int, message_id: int, title: str):
    try:
        return await client.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=title,
            parse_mode=None
        )
    except Exception:
        return None


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

@app.on_message(
    filters.channel & ~filters.service,
    group=10
)
async def handle_bulk_channel(client, message: Message):
    try:
        chat_id = str(message.chat.id)

        if not await is_channel_authed(chat_id):
            return

        if not (message.text or message.document or message.video or message.audio or message.photo):
            return

        async with LOCK:
            bulk_bucket[chat_id].append(message)

            if chat_id in bulk_tasks and not bulk_tasks[chat_id].done():
                bulk_tasks[chat_id].cancel()

            bulk_tasks[chat_id] = asyncio.create_task(
                _flush_bulk(client, chat_id, BULK_WAIT)
            )

    except Exception as e:
        print(f"Bulk handler error: {e}")


def _nearest_title_for_media(messages: list[Message], media_message: Message) -> Optional[str]:
    """Return the nearest title text above a media message."""
    ordered = sorted((m for m in messages if m), key=lambda m: m.id)
    index = next((i for i, m in enumerate(ordered) if m.id == media_message.id), None)
    if index is None:
        return None

    for i in range(index - 1, max(-1, index - 6), -1):
        msg = ordered[i]
        text = (msg.text or "").strip()
        if not text:
            continue
        if re.match(r"^━━+\s*Episode\s+\d+", text, re.IGNORECASE):
            continue
        if parse_episode_title_lines(text):
            fname = media_filename(media_message) or ""
            parsed = title_for_filename(fname, parse_episode_title_lines(text))
            if parsed:
                return parsed
        return text
    return None


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

    title_map = await load_episode_titles(chat_id)
    for source_msg in messages:
        text = (source_msg.text or "").strip()
        if text:
            title_map.update(parse_episode_title_lines(text))

    await save_episode_titles(chat_id, title_map)

    episodes = defaultdict(list)
    for msg in messages:
        fname = media_filename(msg)
        if fname:
            ep_num = _int_episode(fname)
            episodes[ep_num].append(msg)

    sorted_episodes = sorted(episodes.items())
    int_chat_id = int(chat_id)

    for ep_num, msgs_in_episode in sorted_episodes:
        sorted_msgs = sorted(
            msgs_in_episode,
            key=lambda m: _quality_val(media_filename(m) or "")
        )

        episode_title = None
        for media_msg in sorted_msgs:
            fname = media_filename(media_msg) or ""
            episode_title = title_for_filename(fname, title_map)
            if episode_title:
                break
            episode_title = _nearest_title_for_media(messages, media_msg)
            if episode_title:
                break

        if episode_title and episode_header_enabled and ep_num != 9999:
            try:
                display_key = None
                for media_msg in sorted_msgs:
                    fname = media_filename(media_msg) or ""
                    for candidate in title_keys_for_filename(fname):
                        if candidate in title_map:
                            display_key = candidate
                            break
                    if display_key:
                        break
                title_text = display_title_for_key(display_key, episode_title) if display_key else episode_title
                await client.send_message(
                    int_chat_id,
                    title_text,
                    parse_mode=None
                )
                await asyncio.sleep(1)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                print(f"Title message error: {e}")
        elif episode_header_enabled and ep_num != 9999:
            try:
                await client.send_message(
                    int_chat_id,
                    f"━━━ Episode {ep_num:02d} ━━━",
                    parse_mode=None
                )
                await asyncio.sleep(1)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                print(f"Header error: {e}")

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
                await copy_media_preserving_cover(client, int_chat_id, msg, cap)
                await asyncio.sleep(0.5)
                await msg.delete()
                await asyncio.sleep(0.5)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                try:
                    await copy_media_preserving_cover(client, int_chat_id, msg, cap)
                    await msg.delete()
                except Exception:
                    pass
            except Exception as e:
                print(f"Copy error: {e}")

        if ep_num != 9999:
            try:
                await client.send_sticker(int_chat_id, sticker_id)
                await asyncio.sleep(1)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
            except Exception as e:
                print(f"Sticker error: {e}")


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
        all_messages = []

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

            all_messages.extend(m for m in msgs if m)

        all_messages = sorted(
            {m.id: m for m in all_messages}.values(),
            key=lambda m: m.id
        )

        title_map = await load_episode_titles(real_dest_id)
        for source_msg in all_messages:
            text = (source_msg.text or "").strip()
            if text:
                title_map.update(parse_episode_title_lines(text))
        await save_episode_titles(real_dest_id, title_map)

        episodes = defaultdict(list)
        for msg in all_messages:
            fname = media_filename(msg)
            if not fname or not (msg.document or msg.video):
                continue
            episodes[_int_episode(fname)].append(msg)

        for ep_num, msgs_in_episode in sorted(episodes.items()):
            sorted_msgs = sorted(
                msgs_in_episode,
                key=lambda m: _quality_val(media_filename(m) or "")
            )

            episode_title = None
            for media_msg in sorted_msgs:
                fname = media_filename(media_msg) or ""
                episode_title = title_for_filename(fname, title_map)
                if episode_title:
                    break
                episode_title = _nearest_title_for_media(all_messages, media_msg)
                if episode_title:
                    break

            if episode_header_enabled and ep_num != 9999:
                try:
                    header_text = f"━━━ Episode {ep_num:02d} ━━━"
                    if episode_title:
                        display_key = None
                        for media_msg in sorted_msgs:
                            fname = media_filename(media_msg) or ""
                            for candidate in title_keys_for_filename(fname):
                                if candidate in title_map:
                                    display_key = candidate
                                    break
                            if display_key:
                                break
                        if display_key:
                            header_text = display_title_for_key(display_key, episode_title)
                    await client.send_message(
                        dest_int_id,
                        header_text,
                        parse_mode=None
                    )
                    await asyncio.sleep(1)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except Exception as e:
                    print(f"Title/header error (ac): {e}")

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
                    await copy_media_preserving_cover(client, dest_int_id, msg, cap)
                    await asyncio.sleep(0.5)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                    try:
                        await copy_media_preserving_cover(client, dest_int_id, msg, cap)
                    except Exception as e:
                        print(f"Copy retry error (ac): {e}")
                except Exception as e:
                    print(f"Copy error (ac): {e}")

            if ep_num != 9999:
                try:
                    await client.send_sticker(dest_int_id, sticker_id)
                    await asyncio.sleep(1)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value)
                except Exception as e:
                    print(f"Sticker error (ac): {e}")

        await message.reply_text(
            "✅ <b>Auto caption completed for given range!</b>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )


@app.on_message(filters.private & filters.command(["sept"]))
async def set_episode_titles_cmd(client, message: Message):
    try:
        command_text = message.text or ""
        first_line = command_text.splitlines()[0] if command_text.splitlines() else ""
        args = first_line.split()

        link_args = []
        for token in args[1:]:
            match = re.search(r'(?:https?://)?t\.me/c/(\d+)/(\d+)', token)
            if match:
                link_args.append((match.group(1), int(match.group(2))))

        range_start = None
        range_end = None
        channel_id = None

        if len(link_args) >= 2:
            if link_args[0][0] != link_args[1][0]:
                return await message.reply_text(
                    "❌ <b>Start and end links must be from the same channel.</b>",
                    parse_mode=ParseMode.HTML
                )
            channel_id = int(f"-100{link_args[0][0]}")
            range_start = min(link_args[0][1], link_args[1][1])
            range_end = max(link_args[0][1], link_args[1][1])

        if len(link_args) == 1:
            channel_id = int(f"-100{link_args[0][0]}")
            range_start = link_args[0][1]
            range_end = link_args[0][1]

        numeric_args = [int(x) for x in args[1:] if re.fullmatch(r'\d+', x)]
        if len(numeric_args) >= 2 and range_start is None:
            range_start = min(numeric_args[0], numeric_args[1])
            range_end = max(numeric_args[0], numeric_args[1])

        for token in args[1:]:
            if token.startswith("-100") and token[4:].isdigit() and channel_id is None:
                channel_id = int(token)
                break

        title_text = ""
        if message.reply_to_message:
            title_text = (
                message.reply_to_message.text
                or message.reply_to_message.caption
                or ""
            ).strip()

        if not title_text:
            body_lines = command_text.splitlines()[1:]
            title_text = "\n".join(body_lines).strip()

        if not title_text:
            return await message.reply_text(
                "❌ <b>No episode title list found.</b>\n\n"
                "Reply to the raw title list and use two channel message links.\n\n"
                "<b>Format:</b>\n"
                "<code>S01E09 - Did You Do It?!\n"
                "S01E10 - Next Title\n"
                "OVA S01E11 - Extra Episode\n"
                "SP S01E12 - Special</code>",
                parse_mode=ParseMode.HTML
            )

        if channel_id is None:
            return await message.reply_text(
                "❌ <b>Channel range links are required.</b>\n\n"
                "Use:<code>/sept &lt;start_link&gt; &lt;end_link&gt;</code>",
                parse_mode=ParseMode.HTML
            )

        title_map = parse_episode_title_lines(title_text)
        if not title_map:
            return await message.reply_text(
                "❌ <b>No valid episode titles found.</b>\n\n"
                "Use <code>S01E09 - Title</code> format.",
                parse_mode=ParseMode.HTML
            )

        await save_episode_titles(str(channel_id), title_map)

        if range_start is None or range_end is None:
            return await message.reply_text(
                "❌ <b>Invalid message range.</b>",
                parse_mode=ParseMode.HTML
            )

        total = range_end - range_start + 1
        if total > 5000:
            return await message.reply_text(
                "❌ <b>Range is too large.</b> Maximum supported range is 5000 messages.",
                parse_mode=ParseMode.HTML
            )

        updated = 0
        skipped = 0
        remaining = set(title_map.keys())
        msg_ids = list(range(range_start, range_end + 1))
        chunk_size = 200
        media_by_key = defaultdict(list)

        for pos in range(0, len(msg_ids), chunk_size):
            chunk = msg_ids[pos:pos + chunk_size]
            try:
                fetched = await client.get_messages(channel_id, chunk)
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                try:
                    fetched = await client.get_messages(channel_id, chunk)
                except Exception:
                    skipped += len(chunk)
                    continue
            except Exception:
                skipped += len(chunk)
                continue

            for msg in fetched:
                if not msg:
                    continue
                fname = media_filename(msg)
                if not fname or not (msg.document or msg.video):
                    continue

                key = next(
                    (candidate for candidate in title_keys_for_filename(fname) if candidate in title_map),
                    None
                )
                if key:
                    media_by_key[key].append(msg)

        for key, media_messages in sorted(media_by_key.items()):
            media_messages.sort(key=lambda m: m.id)
            first_media = media_messages[0]
            title = title_map[key]

            try:
                changed = await replace_existing_episode_title(
                    client,
                    channel_id,
                    first_media,
                    display_title_for_key(key, title)
                )
                if changed:
                    updated += 1
                    remaining.discard(key)
                else:
                    skipped += 1
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                try:
                    changed = await replace_existing_episode_title(
                        client,
                        channel_id,
                        first_media,
                        display_title_for_key(key, title)
                    )
                    if changed:
                        updated += 1
                        remaining.discard(key)
                    else:
                        skipped += 1
                except Exception:
                    skipped += 1
            except Exception:
                skipped += 1

        await message.reply_text(
            "✅ <b>Episode titles processed.</b>\n\n"
            f"📺 <b>Channel:</b> <code>{channel_id}</code>\n"
            f"📝 <b>Titles:</b> <code>{len(title_map)}</code>\n"
            f"✏️ <b>Updated:</b> <code>{updated}</code>\n"
            f"⚠️ <b>Skipped:</b> <code>{skipped}</code>\n"
            f"🔎 <b>Not matched:</b> <code>{len(remaining)}</code>",
            parse_mode=ParseMode.HTML
        )

    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML
        )
