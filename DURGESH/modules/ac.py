import html
import re
import os
import asyncio
from collections import defaultdict
from typing import Union, Tuple, Optional

from pyrogram import filters, raw
from pyrogram.file_id import FileId
from pyrogram.types import Message, Chat, LinkPreviewOptions
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
    """Extract video quality from filename with formatted tags."""
    if not text:
        return "N/A"

    qpats = [
        (r'[(\[{<]?\s*4kX264\s*[)\]}>]?', "2160p [4K X264]"),
        (r'[(\[{<]?\s*4kx265\s*[)\]}>]?', "2160p [4K X265]"),
        (r'[(\[{<]?\s*4k\s*[)\]}>]?', "2160p [4K]"),
        (r'[(\[{<]?\s*2k\s*[)\]}>]?', "1440p [2K]"),
        (r'[(\[{<]?\s*(\d{3,4})[pP]\s*[)\]}>]?', None),
        (r'\b(\d{3,4})[pP]\b', None),
        (r'\bWEB[.\- ]*DL\b', "WEB-DL"),
        (r'[(\[{<]?\s*HdRip\s*[)\]}>]?|\bHdRip\b', "HDRip"),
    ]

    detected = None
    for pat, repl in qpats:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            detected = repl if repl else m.group(1) + "p"
            break

    if not detected:
        return "N/A"

    if "360" in detected.lower():
        detected = "480p"

    quality_map = {
        "2160p": "2160p [4K]",
        "1440p": "1440p [2K]",
        "1080p": "1080p [FHD]",
        "720p":  "720p [HD]",
        "480p":  "480p [SD]",
        "576p":  "576p [SD]",
    }

    return quality_map.get(detected.lower(), detected)


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
    target_chat_id: Union[int, str],
    msg: Message,
    caption: str,
    message_thread_id: Optional[int] = None,
):
    """Copy media (re-upload) preserving thumb/cover and custom caption.

    Used by in-channel _flush_bulk because Telegram does NOT allow editing
    captions on forwarded messages. Handles FloodWait with fw.value+1 backoff
    and falls back to msg.copy() when send_video() raises unsupported kwargs
    or any API error. Returns the sent Message on success; raises on fatal error.
    """
    if msg.video:
        kwargs = {
            "chat_id": target_chat_id,
            "video": msg.video.file_id,
            "caption": caption,
            "parse_mode": ParseMode.HTML,
            "duration": msg.video.duration,
            "width": msg.video.width,
            "height": msg.video.height,
            "supports_streaming": msg.video.supports_streaming or True,
            "has_spoiler": getattr(msg.video, "has_spoiler", False) or getattr(msg, "has_media_spoiler", False),
        }
        file_name = getattr(msg.video, "file_name", None)
        if file_name:
            kwargs["file_name"] = file_name
        if message_thread_id is not None:
            kwargs["message_thread_id"] = message_thread_id

        cover_obj = getattr(msg.video, "video_cover", None)
        if cover_obj and hasattr(cover_obj, "file_id"):
            kwargs["video_cover"] = cover_obj.file_id
        elif getattr(msg.video, "thumbs", None):
            thumb_obj = msg.video.thumbs[0]
            if hasattr(thumb_obj, "file_id"):
                kwargs["thumb"] = thumb_obj.file_id

        video_start = getattr(msg.video, "video_start_timestamp", None)
        if video_start is not None:
            kwargs["video_start_timestamp"] = video_start

        while True:
            try:
                return await client.send_video(**kwargs)
            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                continue
            except TypeError:
                kwargs.pop("video_cover", None)
                kwargs.pop("video_start_timestamp", None)
                try:
                    return await client.send_video(**kwargs)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                    continue
                except Exception as e:
                    print(f"[ac] send_video fallback to copy: {e}")
                    break
            except Exception as e:
                print(f"[ac] send_video error: {e}")
                break

    # Non-video media: photo/document/audio/animation via msg.copy
    copy_kwargs = {
        "chat_id": target_chat_id,
        "caption": caption,
        "parse_mode": ParseMode.HTML,
    }
    if message_thread_id is not None:
        copy_kwargs["message_thread_id"] = message_thread_id

    while True:
        try:
            return await msg.copy(**copy_kwargs)
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
            continue
        except Exception as e:
            print(f"[ac] msg.copy fatal error mid={msg.id}: {e}")
            raise


async def send_or_forward_media(
    client,
    source_chat_id: int,
    dest_chat_id: int,
    msg: Message,
    caption: str,
    message_thread_id: Optional[int] = None,
    is_source_protected: bool = False,
    no_caption_mode: bool = False,
):
    """
    Intelligently transfer media:
    - Protected channel: copy media directly (send_video / msg.copy).
    - Non-protected: forward without tag (drop_author=True), then edit caption.
    FloodWait is respected with fw.value+1 sleep (never fallback to copy on FloodWait).
    """
    # Forward without tag path (non-protected sources)
    if not is_source_protected:
        try:
            fwd_kwargs = {
                "chat_id": dest_chat_id,
                "from_chat_id": source_chat_id,
                "message_ids": msg.id,
                "drop_author": True,
            }
            if message_thread_id is not None:
                fwd_kwargs["message_thread_id"] = message_thread_id

            fwd_msgs = await client.forward_messages(**fwd_kwargs)
            sent_msg = fwd_msgs[0] if isinstance(fwd_msgs, list) else fwd_msgs

            if not no_caption_mode and caption and caption != (msg.caption or ""):
                try:
                    await sent_msg.edit_caption(caption=caption, parse_mode=ParseMode.HTML)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                    await sent_msg.edit_caption(caption=caption, parse_mode=ParseMode.HTML)
                except Exception as e:
                    print(f"[ac] Caption edit failed: {e}")

            return sent_msg

        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
            return await send_or_forward_media(
                client, source_chat_id, dest_chat_id, msg, caption,
                message_thread_id, is_source_protected, no_caption_mode,
            )
        except Exception as e:
            print(f"[ac] Forward without tag failed ({e}), falling back to copy mode.")
            is_source_protected = True

    # Copy path (protected sources or forward fallback)
    if msg.video:
        kwargs = {
            "chat_id": dest_chat_id,
            "video": msg.video.file_id,
            "caption": caption,
            "parse_mode": ParseMode.HTML,
            "duration": msg.video.duration,
            "width": msg.video.width,
            "height": msg.video.height,
            "supports_streaming": msg.video.supports_streaming or True,
            "has_spoiler": getattr(msg.video, "has_spoiler", False) or getattr(msg, "has_media_spoiler", False),
        }
        if message_thread_id is not None:
            kwargs["message_thread_id"] = message_thread_id

        cover_obj = getattr(msg.video, "video_cover", None)
        if cover_obj and hasattr(cover_obj, "file_id"):
            kwargs["video_cover"] = cover_obj.file_id
        elif getattr(msg.video, "thumbs", None):
            thumb_obj = msg.video.thumbs[0]
            if hasattr(thumb_obj, "file_id"):
                kwargs["thumb"] = thumb_obj.file_id

        video_start = getattr(msg.video, "video_start_timestamp", None)
        if video_start is not None:
            kwargs["video_start_timestamp"] = video_start

        while True:
            try:
                return await client.send_video(**kwargs)
            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                continue
            except TypeError:
                kwargs.pop("video_cover", None)
                kwargs.pop("video_start_timestamp", None)
                try:
                    return await client.send_video(**kwargs)
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                    continue
                except Exception as e:
                    print(f"[ac] send_video fallback to copy: {e}")
                    break
            except Exception as e:
                print(f"[ac] send_video error: {e}")
                break

    copy_kwargs = {
        "chat_id": dest_chat_id,
        "caption": caption,
        "parse_mode": ParseMode.HTML,
    }
    if message_thread_id is not None:
        copy_kwargs["message_thread_id"] = message_thread_id

    while True:
        try:
            return await msg.copy(**copy_kwargs)
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
            continue
        except Exception as e:
            print(f"[ac] msg.copy fatal error: {e}")
            return None


def parse_telegram_link(link: str) -> Tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Parse Telegram message links supporting both 2-part and 3-part topic URLs:
    - https://t.me/c/3951520904/33        -> chat: 3951520904, topic: None, msg_id: 33
    - https://t.me/c/3951520904/31/33     -> chat: 3951520904, topic: 31, msg_id: 33
    Public username links:
    - https://t.me/username/33            -> chat: "@username", topic: None, msg_id: 33
    """
    if not link:
        return None, None, None
    s = link.strip()
    m = re.search(r'(?:https?://)?t\.me/c/(\d+)(?:/(\d+))?/(\d+)', s)
    if m:
        chat_internal = m.group(1)
        if m.group(2) is not None:
            topic_id = int(m.group(2))
            msg_id = int(m.group(3))
        else:
            topic_id = None
            msg_id = int(m.group(3))
        return chat_internal, topic_id, msg_id
    m2 = re.search(r'(?:https?://)?t\.me/([a-zA-Z0-9_]+)/(\d+)', s)
    if m2:
        return "@" + m2.group(1), None, int(m2.group(2))
    return None, None, None


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
        # Prefer new API (Kurigram 2.2+): message.forward_origin.chat.sender_chat
        # Fall back to legacy forward_from_chat for older versions.
        fwd_chat = None
        fo = getattr(r, "forward_origin", None)
        if fo is not None:
            chat = getattr(fo, "chat", None)
            if chat is not None:
                fwd_chat = getattr(chat, "sender_chat", None) or chat
        if fwd_chat is None:
            fwd_chat = getattr(r, "forward_from_chat", None)
        if fwd_chat:
            return str(fwd_chat.id), fwd_chat
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


async def load_sticker(chat_id: Union[int, str]) -> Optional[str]:
    """
    Load custom sticker for chat. Checks both 'sticker_id' and legacy 'sticker' keys,
    falling back to DEFAULT_STICKER.
    """
    try:
        data = await captiondb.find_one({"chat_id": str(chat_id)})
        if not data:
            return DEFAULT_STICKER
        return data.get("sticker_id") or data.get("sticker") or DEFAULT_STICKER
    except Exception as e:
        print(f"[captiondb] Error loading sticker for {chat_id}: {e}")
        return DEFAULT_STICKER


async def load_episode_header_setting(chat_id: Union[int, str]) -> bool:
    """
    Load EPT (Episode Title Header) setting.
    Checks 'ept' override first, then 'episode_header', defaulting to True.
    """
    try:
        data = await captiondb.find_one({"chat_id": str(chat_id)})
        if not data:
            return True
        if "ept" in data:
            return bool(data["ept"])
        return bool(data.get("episode_header", True))
    except Exception as e:
        print(f"[captiondb] Error loading EPT setting for {chat_id}: {e}")
        return True


async def remove_episode_titles(chat_id: str):
    """Delete all stored episode titles for a channel (cleanup / unauth)."""
    await episodetitledb.delete_many({"chat_id": str(chat_id)})


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
        await remove_episode_titles(channel_id)

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
    if message.photo:
        return (message.caption or "").strip() or "Image"
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


def format_episode_title_message(*args) -> str:
    if len(args) == 1 and isinstance(args[0], str):
        return f"<b>{html.escape(args[0].strip())}</b>"
    title_map, ep_num = args[0], args[1]
    try:
        ep_int = int(ep_num)
    except Exception:
        ep_int = 0
    chosen_key = None
    chosen_title = None
    if isinstance(title_map, dict):
        for k, v in title_map.items():
            k_str = str(k).upper()
            m = re.search(r'E(\d+)\s*$', k_str)
            if m and int(m.group(1)) == ep_int:
                chosen_key = k_str
                chosen_title = str(v)
                break
    if chosen_title:
        label = "Episode"
        for prefix in ("OVA", "OAV", "SP", "SPECIAL"):
            if chosen_key.startswith(prefix + "_"):
                label = prefix if prefix != "SPECIAL" else "SP"
                break
        return f"<b>{html.escape(f'{label} {ep_int} – {chosen_title.strip()}')}</b>"
    return f"<b>{html.escape(f'Episode {ep_int:02d}')}</b>"


async def save_episode_titles(chat_id: Union[int, str], title_map: dict):
    """Persist episode titles without requiring prior channel whitelist."""
    if not title_map:
        return
    clean_map = {str(k): str(v) for k, v in title_map.items() if v}
    if not clean_map:
        return
    await episodetitledb.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {"titles": clean_map}},
        upsert=True
    )


async def load_episode_titles(chat_id) -> dict:
    result = {}
    cid = str(chat_id)
    doc = await episodetitledb.find_one({"chat_id": cid})
    if doc and isinstance(doc.get("titles"), dict):
        for k, v in doc["titles"].items():
            if k and v:
                result[str(k)] = str(v)
        return result
    cursor = episodetitledb.find({"chat_id": cid})
    async for d in cursor:
        key = d.get("key")
        title = d.get("title")
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
    """Update the existing episode title message in place."""
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

        await client.edit_message_text(
            chat_id=chat_id,
            message_id=title_message.id,
            text=new_text,
            parse_mode=ParseMode.HTML,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        return True
    except Exception as e:
        print(f"Episode title update error: {e}")
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
bulk_channel_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
BULK_IDLE_SECONDS = 4
POLL_INTERVAL = 1
_CLEANUP_RAN = False


async def cleanup_orphan_episode_titles():
    """Remove episode titles for chats that are no longer authorized."""
    try:
        authed = set(await get_all_auth_channels())
        cursor = episodetitledb.find({}, {"chat_id": 1})
        orphan_ids = set()
        async for doc in cursor:
            cid = str(doc.get("chat_id"))
            if cid and cid not in authed:
                orphan_ids.add(cid)
        for cid in orphan_ids:
            await episodetitledb.delete_many({"chat_id": cid})
        if orphan_ids:
            print(f"[ac] Cleaned orphan episode titles for {len(orphan_ids)} unauth'd chat(s)")
    except Exception as e:
        print(f"[ac] Orphan title cleanup error: {e}")


@app.on_message(filters.private & filters.command(["cleantitles", "ctitles"]))
async def clean_titles_cmd(client, message: Message):
    """Admin command to manually wipe orphaned episode-title DB entries."""
    try:
        before = await episodetitledb.count_documents({})
        await cleanup_orphan_episode_titles()
        after = await episodetitledb.count_documents({})
        await message.reply_text(
            f"🧹 <b>Episode titles cleanup done.</b>\n"
            f"Before: <code>{before}</code> entries\n"
            f"After: <code>{after}</code> entries",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await message.reply_text(
            f"❌ <b>Error:</b> {html.escape(str(e))}",
            parse_mode=ParseMode.HTML,
        )


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


def _episode_media_sort_key(m: Message):
    if m.photo:
        return (-1, 0)
    fname = media_filename(m) or ""
    return (0, _quality_val(fname))


def _int_episode(fname: str) -> int:
    try:
        raw = extract_episode(fname)
        match = re.search(r'(\d+)', raw)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return 9999

def _schedule_startup_cleanup():
    """One-time orphan cleanup shortly after the bot event loop starts."""
    global _CLEANUP_RAN
    if _CLEANUP_RAN:
        return
    _CLEANUP_RAN = True
    try:
        loop = asyncio.get_event_loop()
        loop.call_later(15, lambda: asyncio.ensure_future(cleanup_orphan_episode_titles()))
    except Exception as e:
        print(f"[ac] Could not schedule startup cleanup: {e}")


_schedule_startup_cleanup()


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

        # Append the new message into the bucket under a brief lock.
        # If a flush is currently RUNNING (channel lock held), just append and return —
        # the new message will be picked up by the next scheduler pass.
        if chat_id not in bulk_bucket:
            bulk_bucket[chat_id] = []
        bulk_bucket[chat_id].append(message)

        # Only schedule/restart the debounce watcher.
        # NEVER cancel a running flush task (that was the mid-batch cancellation trap).
        existing = bulk_tasks.get(chat_id)
        if existing is None or existing.done():
            bulk_tasks[chat_id] = asyncio.create_task(
                _bulk_idle_watcher(client, chat_id)
            )

    except Exception as e:
        print(f"Bulk handler error: {e}")


async def _bulk_idle_watcher(client, chat_id: str):
    """Wait-until-idle debounce: poll bucket size until it stays unchanged for
    BULK_IDLE_SECONDS (all forwarded files have landed), then perform the flush
    under a per-channel lock so concurrent arrivals cannot cancel an in-progress batch.
    """
    try:
        last_size = -1
        idle_for = 0
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            cur_size = len(bulk_bucket.get(chat_id, []))
            if cur_size == last_size and cur_size > 0:
                idle_for += POLL_INTERVAL
            else:
                idle_for = 0
                last_size = cur_size
            if cur_size > 0 and idle_for >= BULK_IDLE_SECONDS:
                break
            if cur_size == 0 and idle_for >= BULK_IDLE_SECONDS:
                bulk_tasks.pop(chat_id, None)
                return

        # Acquire per-channel lock so no new handler invocation can interrupt us.
        chan_lock = bulk_channel_locks[chat_id]
        async with chan_lock:
            # Drain the bucket
            messages = list(bulk_bucket.pop(chat_id, []))
            bulk_tasks.pop(chat_id, None)
            if messages:
                await _flush_bulk(client, chat_id, messages)

        # After flush, if new messages arrived while we were processing,
        # immediately re-schedule a new watcher for them.
        if chat_id in bulk_bucket and bulk_bucket[chat_id]:
            existing = bulk_tasks.get(chat_id)
            if existing is None or existing.done():
                bulk_tasks[chat_id] = asyncio.create_task(
                    _bulk_idle_watcher(client, chat_id)
                )
    except asyncio.CancelledError:
        # Watcher can be cancelled by the next message arriving — that's fine,
        # a new watcher will be scheduled. Never propagate during active flush.
        pass
    except Exception as e:
        print(f"[bulk] Idle watcher fatal for chat {chat_id}: {e}")
        import traceback
        traceback.print_exc()
        bulk_tasks.pop(chat_id, None)


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


async def _flush_bulk(client, chat_id: str, messages: list):
    """
    Process a ready batch of in-channel posts (called by _bulk_idle_watcher after
    the idle debounce and under the per-channel lock so runs cannot be cancelled mid-batch):
    - Custom Captions applied to videos/documents.
    - EPT header sent only when episode_header_enabled is True.
    - Separator sticker ALWAYS sent per-episode (INDEPENDENT of EPT).
    - Strict media isolation: ONLY msg.video / msg.document enter episode groups;
      photos & text are treated as title cards and cleaned up at the end.
    - Instant auto-delete of the original forwarded post right after a successful
      captioned re-upload (message_ids as list for cross-version safety).
    - 3-second inter-media spacing; FloodWait sleep+retry at every call site.
    """
    int_chat_id = int(chat_id)

    try:
        if not messages:
            return

        caption_template = await load_caption(chat_id) or DEFAULT_CAPTION
        sticker_id = await load_sticker(chat_id) or DEFAULT_STICKER
        episode_header_enabled = await load_episode_header_setting(chat_id)

        # Episode titles: extract text/captions only when EPT is ON
        title_map = {}
        if episode_header_enabled:
            title_map = await load_episode_titles(chat_id) or {}
            new_titles = False
            for msg in messages:
                text_content = msg.text or msg.caption
                if text_content:
                    parsed = parse_episode_title_lines(text_content)
                    if parsed:
                        title_map.update(parsed)
                        new_titles = True
            if new_titles:
                await save_episode_titles(chat_id, title_map)

        # STRICT media isolation: only video / document become playable media.
        # Photos (title posters) and text are excluded from episode groups.
        episodes = defaultdict(list)
        media_msg_ids = set()

        for msg in messages:
            if not (msg.video or msg.document):
                continue
            fname = media_filename(msg)
            if not fname:
                continue
            ep_num = _int_episode(fname)
            episodes[ep_num].append((fname, msg))
            media_msg_ids.add(msg.id)

        if not episodes:
            all_ids = [m.id for m in messages if m]
            if all_ids:
                try:
                    for i in range(0, len(all_ids), 100):
                        await client.delete_messages(
                            chat_id=int_chat_id, message_ids=all_ids[i:i+100]
                        )
                except Exception as e:
                    print(f"[bulk] Error cleaning non-media batch: {e}")
            return

        sorted_ep_keys = sorted(episodes.keys())

        for ep_num in sorted_ep_keys:
            items_in_ep = episodes[ep_num]
            sorted_items = sorted(items_in_ep, key=lambda item: _quality_val(item[0]))

            # 1. Episode header (only when EPT ON)
            if episode_header_enabled:
                header_text = format_episode_title_message(title_map, ep_num)
                try:
                    await client.send_message(
                        chat_id=int_chat_id,
                        text=header_text,
                        parse_mode=ParseMode.HTML
                    )
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                    try:
                        await client.send_message(
                            chat_id=int_chat_id,
                            text=header_text,
                            parse_mode=ParseMode.HTML
                        )
                    except Exception as e2:
                        print(f"[bulk] Header retry after FloodWait failed for ep {ep_num}: {e2}")
                except Exception as e:
                    print(f"[bulk] Failed to send episode header for ep {ep_num}: {e}")

            # 2. Media items (caption + copy + instant delete)
            for fname, msg in sorted_items:
                filesize = getattr(msg.document or msg.video, "file_size", None)
                duration = getattr(msg.video, "duration", None)
                clean_filename = fname.rsplit(".", 1)[0] if "." in fname else fname
                cap = (
                    caption_template
                    .replace("{filename}", html.escape(str(clean_filename)))
                    .replace("{filesize}", html.escape(str(get_readable_file_size(filesize))))
                    .replace("{duration}", html.escape(str(format_duration(duration))))
                    .replace("{quality}", html.escape(str(extract_quality(fname) or "")))
                    .replace("{season}", html.escape(str(extract_season(fname) or "")))
                    .replace("{episode}", html.escape(str(extract_episode(fname) or "")))
                )

                sent_success = False
                try:
                    await copy_media_preserving_cover(
                        client=client,
                        target_chat_id=int_chat_id,
                        msg=msg,
                        caption=cap
                    )
                    sent_success = True
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                    try:
                        await copy_media_preserving_cover(
                            client=client,
                            target_chat_id=int_chat_id,
                            msg=msg,
                            caption=cap
                        )
                        sent_success = True
                    except Exception as inner_e:
                        print(f"[bulk] Retry copy failed for msg {msg.id}: {inner_e}")
                except Exception as e:
                    print(f"[bulk] Media transmission failed for msg {msg.id}: {e}")

                # Instant delete (LIST form for Kurigram cross-version safety)
                if sent_success:
                    try:
                        await client.delete_messages(
                            chat_id=int_chat_id, message_ids=[msg.id]
                        )
                    except FloodWait as fw:
                        await asyncio.sleep(fw.value + 1)
                        try:
                            await client.delete_messages(
                                chat_id=int_chat_id, message_ids=[msg.id]
                            )
                        except Exception as de2:
                            print(f"[bulk] Delete after FloodWait failed for msg {msg.id}: {de2}")
                    except Exception as del_err:
                        print(
                            f"[bulk] Failed to auto-delete original msg {msg.id}: {del_err}. "
                            f"Ensure 'Delete Messages' permission."
                        )

                await asyncio.sleep(3)

            # 3. Separator sticker — ALWAYS per-episode, independent of EPT
            if sticker_id:
                try:
                    await client.send_sticker(
                        chat_id=int_chat_id, sticker=sticker_id
                    )
                except FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                    try:
                        await client.send_sticker(
                            chat_id=int_chat_id, sticker=sticker_id
                        )
                    except Exception as e2:
                        print(f"[bulk] Sticker retry after FloodWait failed for ep {ep_num}: {e2}")
                except Exception as e:
                    print(f"[bulk] Failed to send separator sticker for ep {ep_num}: {e}")

        # 4. Final sweep: delete orphan non-media (text titles, photo posters, etc.)
        non_media_ids = [m.id for m in messages if m.id not in media_msg_ids]
        if non_media_ids:
            try:
                for i in range(0, len(non_media_ids), 100):
                    batch = non_media_ids[i:i + 100]
                    await client.delete_messages(chat_id=int_chat_id, message_ids=batch)
            except Exception as e:
                print(f"[bulk] Final sweep deletion error: {e}")

    except Exception as fatal_e:
        print(f"[bulk] FATAL crash in _flush_bulk for chat {chat_id}: {fatal_e}")
        import traceback
        traceback.print_exc()


async def auto_cap_cmd(client, message: Message):
    """
    Robust /ac command supporting:
    - Direct execution inside Channel or Forum Topic: /ac <start_link> <end_link> [-noac]
    - Reply Mode: /ac <start_link> <end_link> [-noac]
    - Explicit Mode: /ac <start_link> <end_link> <target_chat> [dest_topic_id] [-noac]
    """
    raw_args = list(message.command[1:])

    no_caption_mode = False
    clean_args = []
    for arg in raw_args:
        if arg.lower() in ("-noac", "-noca", "-no-ca", "--no-caption", "-no_caption"):
            no_caption_mode = True
        else:
            clean_args.append(arg)

    arg_count = len(clean_args)
    reply = message.reply_to_message

    start_arg = None
    end_arg = None
    dest_peer = None
    dest_topic_id = None

    if arg_count >= 2:
        start_arg = clean_args[0]
        end_arg = clean_args[1]

    if arg_count == 2:
        if reply:
            dest_peer = reply.chat.id
            dest_topic_id = getattr(reply, "message_thread_id", None) or getattr(message, "message_thread_id", None)
        else:
            chat_type_name = getattr(getattr(message.chat, "type", None), "name", None) or str(message.chat.type)
            if chat_type_name in ("SUPERGROUP", "GROUP", "CHANNEL", "ChatType.CHANNEL"):
                dest_peer = message.chat.id
                dest_topic_id = getattr(message, "message_thread_id", None)
            else:
                return await message.reply_text(
                    "❌ <b>Target destination required in private DM!</b>\n\n"
                    "<code>/ac &lt;start_link&gt; &lt;end_link&gt; &lt;target_chat_or_link&gt; [-noac]</code>",
                    parse_mode=ParseMode.HTML
                )

    elif arg_count == 3:
        # 3rd arg is topic id if numeric & replying; else destination
        if clean_args[2].lstrip("-").isdigit() and reply:
            dest_peer = reply.chat.id
            dest_topic_id = int(clean_args[2])
        else:
            target_chat_internal, target_topic, _ = parse_telegram_link(clean_args[2])
            if target_chat_internal:
                if isinstance(target_chat_internal, str) and target_chat_internal.startswith("@"):
                    dest_peer = target_chat_internal
                else:
                    dest_peer = int(f"-100{target_chat_internal}")
                dest_topic_id = target_topic
            else:
                dest_peer = normalize_channel_peer(clean_args[2])
                dest_topic_id = getattr(message, "message_thread_id", None)

    elif arg_count >= 4:
        target_chat_internal, target_topic, _ = parse_telegram_link(clean_args[2])
        if target_chat_internal:
            if isinstance(target_chat_internal, str) and target_chat_internal.startswith("@"):
                dest_peer = target_chat_internal
            else:
                dest_peer = int(f"-100{target_chat_internal}")
        else:
            dest_peer = normalize_channel_peer(clean_args[2])
        try:
            dest_topic_id = int(clean_args[3])
        except ValueError:
            dest_topic_id = target_topic
    else:
        usage_text = (
            "<b>Usage Instructions:</b>\n\n"
            "1. <b>Inside Target Channel or Forum Topic:</b>\n"
            "<code>/ac &lt;start_link&gt; &lt;end_link&gt; [-noac]</code>\n\n"
            "2. <b>Via Reply to Message in Target Chat:</b>\n"
            "<code>/ac &lt;start_link&gt; &lt;end_link&gt; [-noac]</code>\n\n"
            "3. <b>With Target Chat and Optional Topic:</b>\n"
            "<code>/ac &lt;start_link&gt; &lt;end_link&gt; &lt;target_chat&gt; [topic_id] [-noac]</code>"
        )
        return await message.reply_text(usage_text, parse_mode=ParseMode.HTML)

    # Parse source links
    src1_chat, _, start_id = parse_telegram_link(start_arg)
    src2_chat, _, end_id = parse_telegram_link(end_arg)

    if not src1_chat or not src2_chat or not start_id or not end_id:
        return await message.reply_text("❌ Please provide valid <code>t.me/c/...</code> links.", parse_mode=ParseMode.HTML)

    if src1_chat != src2_chat:
        return await message.reply_text("❌ Start and end links must be from the same source chat.", parse_mode=ParseMode.HTML)

    # Resolve source chat id
    if isinstance(src1_chat, str) and src1_chat.startswith("@"):
        from_channel = src1_chat
    else:
        from_channel = int(f"-100{src1_chat}")

    # Resolve destination chat
    dest_peer_resolved = dest_peer if isinstance(dest_peer, int) else normalize_channel_peer(dest_peer)
    try:
        dest_chat = await client.get_chat(dest_peer_resolved)
        real_dest_id = str(dest_chat.id)
        dest_int_id = dest_chat.id
    except Exception as e:
        return await message.reply_text(f"❌ Cannot access destination chat: {e}", parse_mode=ParseMode.HTML)

    try:
        member = await client.get_chat_member(dest_int_id, "me")
        if not (member.privileges and member.privileges.can_post_messages):
            return await message.reply_text("❌ <b>Bot lacks posting permissions in destination chat!</b>", parse_mode=ParseMode.HTML)
    except Exception as e:
        return await message.reply_text(f"❌ Unable to verify bot permissions: {e}", parse_mode=ParseMode.HTML)

    if start_id > end_id:
        start_id, end_id = end_id, start_id

    # Load caption & settings (no channel-auth gating)
    caption_template = await load_caption(real_dest_id) or DEFAULT_CAPTION
    sticker_id = await load_sticker(real_dest_id) or DEFAULT_STICKER
    episode_header_enabled = await load_episode_header_setting(real_dest_id)

    try:
        await client.get_chat(from_channel)
    except Exception as e:
        return await message.reply_text(f"❌ Cannot access source chat: {e}", parse_mode=ParseMode.HTML)

    mode_label = "Auto-Arrange Only (-noac)" if no_caption_mode else "Auto-Caption"
    status_msg = await message.reply_text(
        f"⏳ <i>Scanning messages ({mode_label})...</i>",
        parse_mode=ParseMode.HTML
    )

    msg_ids = list(range(start_id, end_id + 1))
    CHUNK = 200
    all_messages = []

    for i in range(0, len(msg_ids), CHUNK):
        chunk_ids = msg_ids[i:i + CHUNK]
        try:
            msgs = await client.get_messages(from_channel, chunk_ids)
            all_messages.extend([m for m in msgs if m and not getattr(m, "empty", False)])
        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
            msgs = await client.get_messages(from_channel, chunk_ids)
            all_messages.extend([m for m in msgs if m and not getattr(m, "empty", False)])
        except Exception as e:
            print(f"[ac] Error fetching chunk: {e}")
            continue

    if not all_messages:
        return await status_msg.edit_text("❌ No messages found in the given range.", parse_mode=ParseMode.HTML)

    # Episode titles (text + photo captions)
    title_map = await load_episode_titles(real_dest_id) or {}
    new_titles_found = False

    for msg in all_messages:
        text_content = msg.text or msg.caption
        if text_content:
            parsed = parse_episode_title_lines(text_content)
            if parsed:
                title_map.update(parsed)
                new_titles_found = True

    if new_titles_found:
        await save_episode_titles(real_dest_id, title_map)

    # Media grouping: STRICTLY videos & documents
    episodes = defaultdict(list)
    for msg in all_messages:
        if not (msg.video or msg.document):
            continue
        fname = media_filename(msg)
        if not fname:
            continue
        ep_num = _int_episode(fname)
        episodes[ep_num].append((fname, msg))

    if not episodes:
        return await status_msg.edit_text("❌ No supported media (videos/documents) found to process.", parse_mode=ParseMode.HTML)

    total_eps = len(episodes)
    total_files = sum(len(v) for v in episodes.values())
    sorted_ep_keys = sorted(episodes.keys())

    breakdown_str = " ".join(str(len(episodes[ep])) for ep in sorted_ep_keys)

    await status_msg.edit_text(
        f"⏳ <b>Processing Task ({mode_label})</b>\n\n"
        f"<b>Total Episodes:</b> <code>{total_eps}</code>\n"
        f"<b>Total Media:</b> <code>{total_files}</code>\n"
        f"<b>Breakdown:</b> <code>{breakdown_str}</code>",
        parse_mode=ParseMode.HTML
    )

    processed_eps = 0

    for ep_num in sorted_ep_keys:
        items_in_ep = episodes[ep_num]
        sorted_items = sorted(items_in_ep, key=lambda item: _quality_val(item[0]))

        # Episode header
        if episode_header_enabled:
            header_text = format_episode_title_message(title_map, ep_num)
            try:
                h_kwargs = dict(
                    chat_id=dest_int_id,
                    text=header_text,
                    parse_mode=ParseMode.HTML,
                )
                if dest_topic_id is not None:
                    h_kwargs["message_thread_id"] = dest_topic_id
                await client.send_message(**h_kwargs)
            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                try:
                    await client.send_message(**h_kwargs)
                except Exception as e2:
                    print(f"[ac] Header retry after FloodWait failed for ep {ep_num}: {e2}")
            except Exception as e:
                print(f"[ac] Failed to send header for ep {ep_num}: {e}")

        # Media items
        for fname, msg in sorted_items:
            if no_caption_mode:
                cap = msg.caption or ""
            else:
                filesize = getattr(msg.document or msg.video, "file_size", None)
                duration = getattr(msg.video, "duration", None)
                clean_filename = fname.rsplit(".", 1)[0] if "." in fname else fname
                cap = (
                    caption_template
                    .replace("{filename}", html.escape(str(clean_filename)))
                    .replace("{filesize}", html.escape(str(get_readable_file_size(filesize))))
                    .replace("{duration}", html.escape(str(format_duration(duration))))
                    .replace("{quality}", html.escape(str(extract_quality(fname) or "")))
                    .replace("{season}", html.escape(str(extract_season(fname) or "")))
                    .replace("{episode}", html.escape(str(extract_episode(fname) or "")))
                )

            try:
                await copy_media_preserving_cover(
                    client=client,
                    target_chat_id=dest_int_id,
                    msg=msg,
                    caption=cap,
                    message_thread_id=dest_topic_id
                )
            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                try:
                    await copy_media_preserving_cover(
                        client=client,
                        target_chat_id=dest_int_id,
                        msg=msg,
                        caption=cap,
                        message_thread_id=dest_topic_id
                    )
                except Exception as inner_e:
                    print(f"[ac] Retry failed for msg {msg.id}: {inner_e}")
                    import traceback
                    traceback.print_exc()
            except Exception as e:
                print(f"[ac] Media dispatch error for msg {msg.id}: {e}")
                import traceback
                traceback.print_exc()

            await asyncio.sleep(3)

        # Episode separator sticker
        if sticker_id:
            try:
                s_kwargs = dict(chat_id=dest_int_id, sticker=sticker_id)
                if dest_topic_id is not None:
                    s_kwargs["message_thread_id"] = dest_topic_id
                await client.send_sticker(**s_kwargs)
            except FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                try:
                    await client.send_sticker(**s_kwargs)
                except Exception as e2:
                    print(f"[ac] Sticker retry after FloodWait failed: {e2}")
            except Exception as e:
                print(f"[ac] Failed to send sticker: {e}")

        processed_eps += 1

        if processed_eps % 5 == 0 or processed_eps == total_eps:
            try:
                await status_msg.edit_text(
                    f"⏳ <b>Processing Task ({mode_label})</b>\n\n"
                    f"<b>Progress:</b> <b>{processed_eps}/{total_eps}</b> episodes done\n"
                    f"<b>Breakdown:</b> <code>{breakdown_str}</code>",
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ <b>Task completed successfully!</b>\n\n"
        f"<b>Total Episodes:</b> <code>{total_eps}</code>\n"
        f"<b>Total Media Sent:</b> <code>{total_files}</code>\n"
        f"<b>Breakdown:</b> <code>{breakdown_str}</code>",
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
