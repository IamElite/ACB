import re
import asyncio
import time
import logging
import unicodedata
from typing import Dict, Optional, Tuple, List

import pyrogram
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from pyrogram.enums import ParseMode, ChatType
from pyrogram.errors import FloodWait

logger = logging.getLogger("buttons")
logging.basicConfig(level=logging.INFO)

# -------------------- BUTTON STYLE ENUM (KURIGRAM / PYROGRAM) -------------------- #
try:
    from pyrogram.enums import ButtonStyle
    RED_STYLE = ButtonStyle.DANGER
    GREEN_STYLE = ButtonStyle.SUCCESS
    BLUE_STYLE = ButtonStyle.PRIMARY
except (ImportError, AttributeError):
    RED_STYLE = "danger"
    GREEN_STYLE = "success"
    BLUE_STYLE = "primary"

COLOR_MAP = {
    "r": RED_STYLE,
    "red": RED_STYLE,
    "danger": RED_STYLE,
    "d": RED_STYLE,
    "g": GREEN_STYLE,
    "green": GREEN_STYLE,
    "success": GREEN_STYLE,
    "s": GREEN_STYLE,
    "b": BLUE_STYLE,
    "blue": BLUE_STYLE,
    "primary": BLUE_STYLE,
    "p": BLUE_STYLE
}

from DURGESH import app
from DURGESH.database import db

authdb = db.auth_channels
btn_templatedb = db.button_templates

DEFAULT_FALLBACK_TEMPLATE = (
    "[❖ View And Get ❖ + {link}]\n"
    "[‧ Movies Hub ‧ + https://t.me/UserAccept1_bot?start=req_SyntaxRealm-t4hkaat] [‧ 18+ Zone ‧ + https://t.me/UserAccept1_bot?start=req_SyntaxRealm-gx2v144]\n"
    "[❍ All Ongoings ❍ + https://t.me/addlist/TZkc53kt100yYjBl]"
)

# -------------------- FONT MAPS & NORMALIZER -------------------- #
FONT_MAPS = {
    "s": (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "ᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"
    ),
    "sm": (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"
    ),
    "sim": (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "𝖠𝖡𝖢𝖣𝖤𝖥𝖦𝖧𝖨𝖩𝖪𝖫𝖬𝖭𝖮𝖯𝖰𝖱𝖲𝖳𝖴𝖵𝖶𝖷𝖸𝖹𝖺𝖻𝖼𝖽𝖾𝖿𝗀𝗁𝗂𝗃𝗄𝗅𝗆𝗇𝗈𝗉𝗊𝗋𝗌𝗍𝗎𝗏𝗐𝗑𝗒𝗓"
    ),
    "san": (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    )
}
FONT_MAPS["a"] = FONT_MAPS["sim"]
FONT_MAPS["b"] = FONT_MAPS["san"]

REVERSE_MAP = {}
for src, dst in FONT_MAPS.values():
    for s_char, d_char in zip(src, dst):
        if d_char not in REVERSE_MAP:
            REVERSE_MAP[d_char] = s_char

def normalize_to_ascii(text: str) -> str:
    """Converts Unicode styled text back to plain ASCII."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join(REVERSE_MAP.get(c, c) for c in nfkd)

def apply_font(text: str, font_style: str) -> str:
    if not text or font_style == "normal":
        return text
    clean_text = normalize_to_ascii(text)
    if font_style in FONT_MAPS:
        src, dst = FONT_MAPS[font_style]
        table = dict(zip(src, dst))
        return "".join(table.get(c, c) for c in clean_text)
    return clean_text

# -------------------- BUTTON PARSER & CREATOR -------------------- #
URL_REGEX = re.compile(
    r'(https?://\S+|tg://\S+|@[a-zA-Z0-9_]{4,}|\{\s*(?:link|url|target)\s*\})',
    re.IGNORECASE
)

def sanitize_button_url(url: str) -> Optional[str]:
    if not url:
        return None
    clean = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\u00a0\r\n]+', '', url.strip().strip("'\"<>`"))
    if re.match(r'^\{\s*(?:link|url|target)\s*\}$', clean, re.IGNORECASE):
        return "https://t.me/SyntaxRealm"
    if clean.startswith("@"):
        return f"https://t.me/{clean.lstrip('@')}"
    if custom_tg := re.match(r'^([a-zA-Z0-9_]{4,})\.t\.me(?:/(.*))?$', clean, re.IGNORECASE):
        ch = custom_tg.group(1)
        path = custom_tg.group(2)
        return f"https://t.me/{ch}{'/' + path if path else ''}"
    if re.match(r'^(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/', clean, re.IGNORECASE):
        return f"https://{clean}"
    if not clean.startswith(("http://", "https://", "tg://")):
        if re.match(r'^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}', clean):
            return f"https://{clean}"
        return None
    return clean

def create_button(text: str, url: str, style=RED_STYLE) -> InlineKeyboardButton:
    if style is not None:
        try:
            return InlineKeyboardButton(text, url=url, style=style)
        except (TypeError, ValueError):
            try:
                style_val = getattr(style, "value", str(style).lower())
                return InlineKeyboardButton(text, url=url, style=style_val)
            except Exception:
                pass
    return InlineKeyboardButton(text, url=url)

def parse_buttons(text: str, font_style: str = "sim", default_color=RED_STYLE) -> Optional[InlineKeyboardMarkup]:
    """
    Parses templates supporting:
    - 1-2-1 grid layout: Buttons on the same line separated by spaces stay side-by-side.
    - Connected brackets '][' without spaces start a new row.
    - Preserves '+' in labels (e.g., '18+ Zone').
    - Defaults all buttons to Red / Danger.
    """
    if not text:
        return None

    formatted_text = text.replace('\\n', '\n')
    formatted_text = re.sub(r'\](?!\s)\[', ']\n[', formatted_text)

    raw_lines = formatted_text.strip().splitlines()
    keyboard: List[List[InlineKeyboardButton]] = []

    for line in raw_lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        sub_rows = line_clean.split('//')
        for sub in sub_rows:
            sub = sub.strip()
            if not sub:
                continue

            row: List[InlineKeyboardButton] = []
            matches = re.finditer(r'\[([^\]]+)\](?:\s*[:\-–—|]?\s*\[?\(?([a-zA-Z]+)\)?\]?)?', sub)
            for match in matches:
                content = match.group(1).strip()
                out_color = (match.group(2) or "").strip().lower()

                url_match = URL_REGEX.search(content)
                if url_match:
                    label = content[:url_match.start()].strip()
                    label = re.sub(r'[\s+|:–—\->]+$', '', label).strip()
                    raw_url = url_match.group(1).strip()
                    in_color = content[url_match.end():].strip().lower()
                    in_color = re.sub(r'^[\s+|:–—\->]+', '', in_color).strip()
                else:
                    parts = re.split(r'\s*(?:\+|\->|\|)\s*', content)
                    if len(parts) < 2:
                        continue
                    label = parts[0].strip()
                    raw_url = parts[1].strip()
                    in_color = parts[2].strip().lower() if len(parts) > 2 else ""

                clean_url = sanitize_button_url(raw_url)
                if not label or not clean_url:
                    continue

                btn_color = COLOR_MAP.get(in_color or out_color, default_color)
                styled_text = apply_font(label, font_style) if font_style != "normal" else label
                row.append(create_button(styled_text, clean_url, style=btn_color))

            if row:
                keyboard.append(row)

    return InlineKeyboardMarkup(keyboard) if keyboard else None

# -------------------- DATABASE HELPERS -------------------- #
def parse_time_to_seconds(time_str: str) -> int:
    if not time_str:
        return 1
    if match := re.match(r'^(\d+)([smhd])$', time_str.strip().lower()):
        multiplier = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(match.group(2), 1)
        return int(match.group(1)) * multiplier
    return 1

async def add_auth_channel(chat_id: int, forward_tag: bool = True, auto_accept_time: str = "1s", admin_id: Optional[int] = None):
    cid_str = str(chat_id)
    payload = {
        "chat_id": cid_str,
        "forward_tag_removal": forward_tag,
        "auto_accept_time": auto_accept_time,
        "auto_accept_seconds": parse_time_to_seconds(auto_accept_time)
    }
    if admin_id:
        payload["admin_id"] = str(admin_id)
    await authdb.update_one(
        {"$or": [{"chat_id": cid_str}, {"chat_id": chat_id}]},
        {"$set": payload},
        upsert=True
    )

async def remove_auth_channel(chat_id: int):
    cid_str = str(chat_id)
    await authdb.delete_many({"$or": [{"chat_id": cid_str}, {"chat_id": chat_id}]})

async def get_channel_settings(chat_id: int, username: Optional[str] = None) -> Optional[Dict]:
    cid_str = str(chat_id)
    queries: List[Dict] = [{"chat_id": cid_str}]
    try:
        queries.append({"chat_id": int(cid_str)})
    except Exception:
        pass
    if username:
        u = username.lstrip("@").lower()
        queries.extend([{"chat_id": f"@{u}"}, {"chat_id": u}])

    if data := await authdb.find_one({"$or": queries}):
        return {
            "chat_id": data.get("chat_id"),
            "forward_tag_removal": data.get("forward_tag_removal", True),
            "auto_accept_time": data.get("auto_accept_time", "1s"),
            "auto_accept_seconds": data.get("auto_accept_seconds", 1),
            "admin_id": data.get("admin_id")
        }
    return None

async def is_channel_authed(chat_id: int, username: Optional[str] = None) -> bool:
    return bool(await get_channel_settings(chat_id, username))

async def save_button_template(user_id: int, template: str, font_style: str = "sim"):
    uid_str = str(user_id)
    now = time.time()
    await btn_templatedb.update_one(
        {"$or": [{"user_id": uid_str}, {"user_id": user_id}]},
        {"$set": {"user_id": uid_str, "template": template, "font_style": font_style, "updated_at": now}},
        upsert=True
    )
    await btn_templatedb.update_one(
        {"_id": "GLOBAL_ACTIVE_TEMPLATE"},
        {"$set": {"template": template, "font_style": font_style, "updated_at": now, "admin_id": uid_str}},
        upsert=True
    )

async def get_button_template(user_id: int) -> Optional[Dict]:
    uid_str = str(user_id)
    return await btn_templatedb.find_one({"$or": [{"user_id": uid_str}, {"user_id": user_id}]})

async def get_effective_template(chat_id: int, username: Optional[str] = None) -> Dict:
    settings = await get_channel_settings(chat_id, username)
    if settings and settings.get("admin_id"):
        if tmpl := await get_button_template(settings["admin_id"]):
            if tmpl.get("template"):
                return tmpl

    if global_tmpl := await btn_templatedb.find_one({"_id": "GLOBAL_ACTIVE_TEMPLATE"}):
        if global_tmpl.get("template"):
            return global_tmpl

    if last_tmpl := await btn_templatedb.find_one({"template": {"$exists": True, "$ne": ""}}):
        return last_tmpl

    return {"template": DEFAULT_FALLBACK_TEMPLATE, "font_style": "sim"}

async def delete_button_template(user_id: int):
    uid_str = str(user_id)
    await btn_templatedb.delete_many({"$or": [{"user_id": uid_str}, {"user_id": user_id}]})

# -------------------- MESSAGE HELPERS -------------------- #
def get_forward_chat(msg: Optional[Message]):
    if not msg:
        return None
    origin = getattr(msg, "forward_origin", None)
    if origin:
        chat = getattr(origin, "chat", None)
        if chat:
            return getattr(chat, "sender_chat", chat)
        sender = getattr(origin, "sender_chat", None)
        if sender:
            return sender
    if not hasattr(msg, "forward_origin"):
        try:
            return getattr(msg, "forward_from_chat", None)
        except Exception:
            return None
    return None

def is_forwarded_post(msg: Message) -> bool:
    if getattr(msg, "forward_origin", None) is not None:
        return True
    return bool(getattr(msg, "forward_date", None))

def extract_chat_and_msg_id(link: str) -> Tuple[Optional[int], Optional[int]]:
    if priv := re.match(r"https?://t\.me/c/(-?\d+)/(\d+)", link.strip()):
        raw = priv.group(1).lstrip("-")
        return (int(f"-{raw}") if raw.startswith("100") else int(f"-100{raw}")), int(priv.group(2))
    return None, None

def _entity_name(entity_type) -> str:
    if hasattr(entity_type, "name"):
        return str(entity_type.name).upper()
    val = getattr(entity_type, "value", entity_type)
    if isinstance(val, str):
        return val.upper()
    if hasattr(val, "__name__"):
        return val.__name__.upper()
    return str(val).upper()

ENTITY_TAGS = {
    "BOLD": ("<b>", "</b>"),
    "ITALIC": ("<i>", "</i>"),
    "CODE": ("<code>", "</code>"),
    "STRIKETHROUGH": ("<s>", "</s>"),
    "UNDERLINE": ("<u>", "</u>"),
    "SPOILER": ("<spoiler>", "</spoiler>"),
    "BLOCKQUOTE": ("<blockquote>", "</blockquote>"),
    "EXPANDABLE_BLOCKQUOTE": ("<blockquote expandable>", "</blockquote>")
}

def get_html_text(text: str, entities: list) -> str:
    if not text or not entities:
        return text or ""
    try:
        text_16 = text.encode('utf-16-le')
    except Exception:
        return text

    events = {}
    for i, e in enumerate(entities):
        start = e.offset * 2
        end = (e.offset + e.length) * 2
        t_name = _entity_name(e.type)

        start_tag, end_tag = ENTITY_TAGS.get(t_name, ("", ""))
        if not start_tag:
            if "PRE" in t_name:
                lang = getattr(e, "language", "") or ""
                start_tag, end_tag = f'<pre><code class="language-{lang}">', "</code></pre>"
            elif "TEXT_LINK" in t_name and hasattr(e, "url"):
                start_tag, end_tag = f'<a href="{e.url}">', "</a>"
            elif "TEXT_MENTION" in t_name and hasattr(e, "user") and e.user:
                start_tag, end_tag = f'<a href="tg://user?id={e.user.id}">', "</a>"

        if start_tag:
            events.setdefault(start, []).append(('start', i, start_tag))
            events.setdefault(end, []).append(('end', i, end_tag))

    res = ""
    last_idx = 0
    for idx in sorted(events.keys()):
        res += text_16[last_idx:idx].decode('utf-16-le')
        evs = events[idx]
        for e in sorted([x for x in evs if x[0] == 'end'], key=lambda x: x[1], reverse=True):
            res += e[2]
        for e in sorted([x for x in evs if x[0] == 'start'], key=lambda x: x[1]):
            res += e[2]
        last_idx = idx

    res += text_16[last_idx:].decode('utf-16-le')
    return res

TRIGGER_REGEX = re.compile(
    r'[-–—•▪►👉🔗~]+\s*(?:<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\'][^>]*>.*?</a>|(https?://\S+|tg://\S+|t\.me/\S+))',
    re.IGNORECASE
)

def extract_trigger_link_and_clean_caption(raw_text: str, html_text: str) -> Tuple[Optional[str], str, str]:
    if not raw_text and not html_text:
        return None, "", ""

    target_text = html_text or raw_text
    match = TRIGGER_REGEX.search(target_text)
    if not match:
        return None, raw_text, html_text

    extracted_url = match.group(1) or match.group(2)
    if extracted_url:
        extracted_url = extracted_url.strip().strip("'\"<>`")

    cl_html = TRIGGER_REGEX.sub('', target_text).strip()
    cl_raw = TRIGGER_REGEX.sub('', raw_text).strip() if raw_text else cl_html

    return extracted_url, cl_raw, cl_html

# -------------------- HYPERLINK & CAPTION FORMATTER -------------------- #
SYNTAX_CREDIT_HTML = '<a href="https://t.me/SyntaxRealm">˹ 𝖲𝗒𝗇𝗍𝖺𝖷𝖱𝖾𝖺𝗅𝗆.𝗍.𝗆𝖾 ˼</a>'
SYNTAX_CREDIT_PLAIN = '˹ https://t.me/SyntaxRealm ˼'

SYNTAX_PATTERN = re.compile(
    r"""['"`‘ʼ՚]?\s*(?:˹\s*)?(?:SyntaxRealm|𝖲𝗒𝗇𝗍𝖺𝖷𝖱𝖾𝖺𝗅𝗆|ꜱʏɴᴛᴀxʀᴇᴀʟᴍ|Syntax[\s_-]*Realm)(?:\.t\.me|\.𝗍\.𝗆𝖾)?(?:\s*˼)?\s*['"`’ʼ՚,]?""",
    re.IGNORECASE
)

def hyperlink_syntax_realm(text: str, is_html: bool = True) -> str:
    if not text:
        return text

    target_replacement = SYNTAX_CREDIT_HTML if is_html else SYNTAX_CREDIT_PLAIN
    if 'href="https://t.me/SyntaxRealm"' in text or 'https://t.me/SyntaxRealm' in text:
        return text

    if SYNTAX_PATTERN.search(text):
        return SYNTAX_PATTERN.sub(target_replacement, text)

    norm = normalize_to_ascii(text).lower()
    if "syntaxrealm" in norm:
        return re.sub(
            r"""['"`‘ʼ՚]?\s*(?:˹\s*)?syntaxrealm(?:\.t\.me)?(?:\s*˼)?\s*['"`’ʼ՚,]?""",
            target_replacement,
            text,
            flags=re.IGNORECASE
        )
    return text

def apply_font_to_caption(caption: str, font_style: str, is_html: bool = True) -> str:
    if not caption:
        return ""

    pattern = re.compile(r'(<[^>]+>|https?://[^\s]+|t\.me/[^\s]+|tg://[^\s]+)')
    lines = []
    for line in caption.split('\n'):
        norm_line = normalize_to_ascii(line).lower()
        if "syntaxrealm" in norm_line or "made by" in norm_line or "credit" in norm_line:
            lines.append(hyperlink_syntax_realm(line, is_html=is_html))
            continue

        if font_style == "normal":
            lines.append(line)
            continue

        parts = pattern.split(line)
        styled = [
            p if (p.startswith('<') and p.endswith('>')) or p.startswith(('http', 't.me', 'tg://'))
            else apply_font(p, font_style)
            for p in parts if p
        ]
        lines.append(''.join(styled))

    formatted_caption = '\n'.join(lines)
    return hyperlink_syntax_realm(formatted_caption, is_html=is_html)

async def repost_with_buttons_and_delete_old(
    client,
    msg: Message,
    chat_id: int,
    caption: str,
    raw_caption: str,
    reply_markup: InlineKeyboardMarkup
) -> bool:
    """
    Guarantees post creation even if channel has content restrictions (anti-save / no forwards).
    Uses file_id directly so Telegram cannot block copy or forward.
    """
    for mode, cap_text in [(ParseMode.HTML, caption), (None, raw_caption)]:
        try:
            sent = None
            if msg.media:
                if msg.photo:
                    sent = await client.send_photo(chat_id, msg.photo.file_id, caption=cap_text, parse_mode=mode, reply_markup=reply_markup)
                elif msg.video:
                    sent = await client.send_video(chat_id, msg.video.file_id, caption=cap_text, parse_mode=mode, reply_markup=reply_markup)
                elif msg.document:
                    sent = await client.send_document(chat_id, msg.document.file_id, caption=cap_text, parse_mode=mode, reply_markup=reply_markup)
                elif msg.audio:
                    sent = await client.send_audio(chat_id, msg.audio.file_id, caption=cap_text, parse_mode=mode, reply_markup=reply_markup)
                elif msg.animation:
                    sent = await client.send_animation(chat_id, msg.animation.file_id, caption=cap_text, parse_mode=mode, reply_markup=reply_markup)
                else:
                    sent = await msg.copy(chat_id, caption=cap_text, parse_mode=mode, reply_markup=reply_markup)
            else:
                sent = await client.send_message(chat_id, text=cap_text, parse_mode=mode, reply_markup=reply_markup, disable_web_page_preview=False)

            if sent:
                await asyncio.sleep(0.3)
                try:
                    await msg.delete()
                except Exception as del_err:
                    logger.warning(f"[AUTO-BUTTON] Could not delete old post {msg.id}: {del_err}")
                return True

        except FloodWait as fw:
            await asyncio.sleep(fw.value + 2)
            continue
        except Exception as send_err:
            logger.warning(f"[AUTO-BUTTON] Send attempt failed with mode={mode}: {send_err}")
            continue

    return False

# -------------------- COMMAND HANDLERS -------------------- #
@app.on_message(filters.command(["auth"]))
async def auth_cmd(client, message: Message):
    args = message.text.split()
    forward_tag = "-f" in args and args[args.index("-f") + 1].lower() in ["on", "true", "1"] if "-f" in args and args.index("-f") + 1 < len(args) else True
    auto_accept = args[args.index("-ac") + 1] if "-ac" in args and args.index("-ac") + 1 < len(args) else "1s"

    chat_id = None
    if fwd := get_forward_chat(message.reply_to_message):
        chat_id = fwd.id
    elif len(args) >= 2:
        try:
            chat_id = (await client.get_chat(args[1])).id if args[1].startswith("@") else int(args[1])
        except Exception as e:
            return await message.reply_text(f"❌ Invalid channel! Error: {e}")

    if not chat_id:
        return await message.reply_text("❌ Usage: `/auth <channel_id> -f on/off -ac 1s`")

    admin_id = message.from_user.id if message.from_user else None
    await add_auth_channel(chat_id, forward_tag, auto_accept, admin_id=admin_id)
    await message.reply_text(
        f"✅ **Channel Authorized!**\n🆔 `{chat_id}`\n🔄 Forward Tag Removal: `{'ON' if forward_tag else 'OFF'}`\n⏱ Auto-Accept: `{auto_accept}`"
    )

@app.on_message(filters.command(["unauth"]))
async def unauth_cmd(client, message: Message):
    chat_id = None
    if len(message.command) >= 2:
        try:
            chat_id = (await client.get_chat(message.command[1])).id if message.command[1].startswith("@") else int(message.command[1])
        except Exception:
            return await message.reply_text("❌ Invalid channel!")
    elif fwd := get_forward_chat(message.reply_to_message):
        chat_id = fwd.id

    if not chat_id:
        return await message.reply_text("❌ Usage: `/unauth <channel_id>`")

    await remove_auth_channel(chat_id)
    await message.reply_text(f"✅ Un-Authorized: `{chat_id}`")

@app.on_message(filters.command(["abset", "absee", "abseen", "abrm"]))
async def template_mgmt_handler(client, message: Message):
    cmd = message.command[0].lower()
    user_id = message.from_user.id if message.from_user else 0

    if cmd == "abrm":
        await delete_button_template(user_id)
        return await message.reply_text("🗑️ Template remove kar diya gaya hai!")

    if cmd in ["absee", "abseen"]:
        data = await get_button_template(user_id) or await btn_templatedb.find_one({"_id": "GLOBAL_ACTIVE_TEMPLATE"})
        tmpl_str = data.get("template", DEFAULT_FALLBACK_TEMPLATE) if data else DEFAULT_FALLBACK_TEMPLATE
        font_st = data.get("font_style", "sim") if data else "sim"

        preview_text = tmpl_str.replace("{link}", "https://t.me/PreviewDemo")
        preview_keyboard = parse_buttons(preview_text, font_style=font_st, default_color=RED_STYLE)
        return await message.reply_text(
            f"📋 **Aapka Button Template:**\n`{tmpl_str}`\n\n🎨 **Font:** `{font_st}`\n👇 **Button Preview:**",
            reply_markup=preview_keyboard
        )

    if cmd == "abset":
        text = message.text or message.caption or ""
        font_style = "sim"
        if font_match := re.search(r"-f\s+(\w+)", text):
            font_style = font_match.group(1).lower()

        if message.reply_to_message and (message.reply_to_message.text or message.reply_to_message.caption):
            template_text = message.reply_to_message.text or message.reply_to_message.caption
        else:
            template_text = re.sub(r"^/abset\s*", "", text, flags=re.IGNORECASE)
            template_text = re.sub(r"-f\s+\w+", "", template_text, flags=re.IGNORECASE).strip()

        if not template_text:
            return await message.reply_text(
                "❌ **Template text provide karein! Format:**\n"
                "`/abset [❖ View And Get ❖ + {link}]\n"
                "[‧ Movies Hub ‧ + https://t.me/Link1] [‧ 18+ Zone ‧ + https://t.me/Link2]\n"
                "[❍ All Ongoings ❍ + https://t.me/Link3]`"
            )

        test_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", "https://t.me/PreviewDemo", template_text, flags=re.IGNORECASE)
        test_keyboard = parse_buttons(test_text, font_style=font_style, default_color=RED_STYLE)
        if not test_keyboard:
            return await message.reply_text("❌ Koi valid button nahi mila! Please check your bracket format.")

        await save_button_template(user_id, template_text, font_style)
        return await message.reply_text(
            f"✅ **Button Template Set Ho Gaya!**\n🎨 **Font:** `{font_style}`\n🔴 **Default Color:** `Danger (Red)`\n👇 **Live Preview (1-2-1 Grid):**",
            reply_markup=test_keyboard
        )

@app.on_message(filters.command(["ab"]))
async def manual_ab_cmd(client, message: Message):
    args = message.command[1:]
    if not args:
        return await message.reply_text("❌ Usage: `/ab <target_post_link>`")

    target_link = args[0]
    channel_id, msg_id = extract_chat_and_msg_id(target_link)
    if not channel_id:
        if pub := re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", target_link):
            try:
                channel_id, msg_id = (await client.get_chat(pub.group(1))).id, int(pub.group(2))
            except Exception as e:
                return await message.reply_text(f"❌ Channel nahi mila: {e}")
        else:
            return await message.reply_text("❌ Invalid post link format!")

    replacement_link = None
    if message.reply_to_message:
        replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        if m := re.search(r"(https?://\S+)", replied_text):
            replacement_link = m.group(1)

    template_data = await get_button_template(message.from_user.id) or await get_effective_template(channel_id)
    template = template_data.get("template", DEFAULT_FALLBACK_TEMPLATE)
    font_style = template_data.get("font_style", "sim")

    try:
        target_msg = await client.get_messages(channel_id, msg_id)
        original_text = target_msg.caption or target_msg.text or ""
        original_entities = target_msg.caption_entities or target_msg.entities

        if not replacement_link:
            html_text = get_html_text(original_text, original_entities)
            ext_url, cl_raw, cl_html = extract_trigger_link_and_clean_caption(original_text, html_text)
            if ext_url:
                replacement_link = ext_url
                original_text = cl_html

        if not replacement_link and "{link}" in template.lower():
            return await message.reply_text("❌ Replacement link nahi mila! Link reply karein ya post me -link dalein.")

        btn_str = re.sub(r"\{\s*(?:link|url|target)\s*\}", replacement_link or "", template, flags=re.IGNORECASE)
        keyboard = parse_buttons(btn_str, font_style=font_style, default_color=RED_STYLE)
        if not keyboard:
            return await message.reply_text("❌ Buttons parse nahi ho paye.")

        formatted_caption = apply_font_to_caption(original_text, font_style, is_html=True)

        if target_msg.media:
            await client.edit_message_caption(channel_id, msg_id, caption=formatted_caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        else:
            await client.edit_message_text(channel_id, msg_id, text=formatted_caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)

        await message.reply_text("✅ **Buttons & Caption Successfully Applied!**")
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" in str(e).upper():
            await message.reply_text("ℹ️ **Post pehle se updated hai!**")
        else:
            await message.reply_text(f"⚠️ Edit fail: {e}")

@app.on_message(filters.command(["cb"]))
async def change_buttons_cmd(client, message: Message):
    if not message.reply_to_message or not (message.reply_to_message.text or message.reply_to_message.caption):
        return await message.reply_text("❌ Reply to a button-template message with `/cb <post_link>`")
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage: `/cb <post_link>`")

    link = message.command[1]
    channel_id, msg_id = extract_chat_and_msg_id(link)
    if not channel_id:
        if pub := re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", link):
            try:
                channel_id, msg_id = (await client.get_chat(pub.group(1))).id, int(pub.group(2))
            except Exception as e:
                return await message.reply_text(f"❌ Channel error: {e}")
        else:
            return await message.reply_text("❌ Invalid link format!")

    raw_btn = message.reply_to_message.text or message.reply_to_message.caption
    keyboard = parse_buttons(raw_btn, font_style="normal", default_color=RED_STYLE)
    if not keyboard:
        return await message.reply_text("❌ Invalid button layout!")

    try:
        await client.edit_message_reply_markup(channel_id, msg_id, reply_markup=keyboard)
        await message.reply_text("✅ Buttons updated successfully!")
    except Exception as e:
        await message.reply_text(f"⚠️ Update error: {e}")

# -------------------- AUTOMATIC CHANNEL POST DISPATCHER -------------------- #
async def dispatch_channel_post(client, message: Message):
    try:
        # STRICT CHANNEL ONLY: Never touch groups, supergroups, or private chats
        c_type = str(getattr(message.chat, "type", "")).lower()
        if "channel" not in c_type or "supergroup" in c_type or "group" in c_type:
            return

        raw_text = message.caption or message.text or ""
        if not raw_text:
            return

        # STRICT TRIGGER CHECK: Look for -, –, —, •, etc. followed by link
        if not TRIGGER_REGEX.search(raw_text):
            return

        chat_id = message.chat.id
        entities = message.caption_entities or message.entities
        html_text = get_html_text(raw_text, entities)
        extracted_url, cl_raw, cl_html = extract_trigger_link_and_clean_caption(raw_text, html_text)

        if not extracted_url:
            return

        logger.info(f"[AUTO-BUTTON] Channel {chat_id} detected trigger url: {extracted_url}")

        tmpl_data = await get_effective_template(chat_id, message.chat.username)
        font_style = tmpl_data.get("font_style", "sim")
        btn_text = tmpl_data.get("template", DEFAULT_FALLBACK_TEMPLATE)
        btn_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", extracted_url, btn_text, flags=re.IGNORECASE)

        keyboard = parse_buttons(btn_text, font_style=font_style, default_color=RED_STYLE)
        if not keyboard:
            logger.warning("[AUTO-BUTTON] Button parsing failed.")
            return

        final_caption = apply_font_to_caption(cl_html, font_style, is_html=True)
        raw_caption = apply_font_to_caption(cl_raw, font_style, is_html=False)

        # Attempt in-place edit first
        edit_success = False
        try:
            if message.media:
                await client.edit_message_caption(chat_id, message.id, caption=final_caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                await client.edit_message_text(chat_id, message.id, text=final_caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            edit_success = True
            logger.info(f"[AUTO-BUTTON] In-place edit succeeded for post {message.id}")
        except Exception as edit_err:
            err_str = str(edit_err).upper()
            if "MESSAGE_NOT_MODIFIED" in err_str:
                try:
                    await client.edit_message_reply_markup(chat_id, message.id, reply_markup=keyboard)
                    edit_success = True
                except Exception:
                    pass
            else:
                logger.info(f"[AUTO-BUTTON] Cannot edit in-place ({edit_err}). Re-posting with file_id...")

        # If editing fails (other admin's post, protected channel, author rights), re-post and delete original
        if not edit_success:
            reposted = await repost_with_buttons_and_delete_old(
                client=client,
                msg=message,
                chat_id=chat_id,
                caption=final_caption,
                raw_caption=raw_caption,
                reply_markup=keyboard
            )
            if reposted:
                logger.info(f"[AUTO-BUTTON] Successfully re-posted message {message.id} with red buttons.")
            else:
                logger.error(f"[AUTO-BUTTON] Failed to re-post message {message.id}.")

    except Exception as e:
        logger.error(f"[AUTO-BUTTON] Error in dispatch_channel_post: {e}", exc_info=True)

# -------------------- LISTENERS (STRICTLY BROADCAST CHANNELS) -------------------- #
@app.on_message(filters.channel)
async def channel_post_listener(client, message: Message):
    await dispatch_channel_post(client, message)

@app.on_edited_message(filters.channel)
async def channel_post_edit_listener(client, message: Message):
    await dispatch_channel_post(client, message)

@app.on_chat_join_request()
async def auto_approve_join_request(client, request: ChatJoinRequest):
    if settings := await get_channel_settings(request.chat.id):
        await asyncio.sleep(settings["auto_accept_seconds"])
        try:
            await client.approve_chat_join_request(chat_id=request.chat.id, user_id=request.from_user.id)
        except Exception:
            pass