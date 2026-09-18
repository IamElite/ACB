import re
import asyncio
import time
import logging
from typing import Dict, Optional, Tuple, List, Union

import pyrogram
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest, Update
from pyrogram.enums import ParseMode, ChatType

logger = logging.getLogger("buttons")
logger.setLevel(logging.INFO)

try:
    from pyrogram.enums import ButtonStyle
    RED_STYLE = ButtonStyle.DANGER
    GREEN_STYLE = ButtonStyle.SUCCESS
    BLUE_STYLE = ButtonStyle.PRIMARY
    COLORED_BUTTONS_SUPPORTED = True
except (ImportError, AttributeError):
    RED_STYLE = None
    GREEN_STYLE = None
    BLUE_STYLE = None
    COLORED_BUTTONS_SUPPORTED = False
    logger.warning("ButtonStyle not available - colored buttons disabled")

COLOR_MAP = {
    "r": RED_STYLE, "red": RED_STYLE, "danger": RED_STYLE, "d": RED_STYLE,
    "g": GREEN_STYLE, "green": GREEN_STYLE, "success": GREEN_STYLE, "s": GREEN_STYLE,
    "b": BLUE_STYLE, "blue": BLUE_STYLE, "primary": BLUE_STYLE, "p": BLUE_STYLE
}

from DURGESH import app
from DURGESH.database import db

authdb = db.auth_channels
btn_templatedb = db.button_templates

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
        "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗉𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    )
}
FONT_MAPS["a"] = FONT_MAPS["sim"]
FONT_MAPS["b"] = FONT_MAPS["san"]

REVERSE_MAP = {}
for src, dst in FONT_MAPS.values():
    for s_char, d_char in zip(src, dst):
        if d_char not in REVERSE_MAP:
            REVERSE_MAP[d_char] = s_char

def apply_font(text: str, font_style: str) -> str:
    if not text or font_style == "normal":
        return text
    clean_text = "".join(REVERSE_MAP.get(c, c) for c in text)
    if font_style in FONT_MAPS:
        src, dst = FONT_MAPS[font_style]
        table = dict(zip(src, dst))
        return "".join(table.get(c, c) for c in clean_text)
    return clean_text

URL_REGEX = re.compile(r'(https?://\S+|tg://\S+|@[a-zA-Z0-9_]{4,})')

def sanitize_button_url(url: str) -> Optional[str]:
    if not url:
        return None
    clean = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\u00a0\r\n]+', '', url.strip().strip("'\"<>`"))
    if re.match(r'^\{.*\}$', clean):
        return None
    if clean.startswith("@"):
        return f"https://t.me/{clean.lstrip('@')}"
    if custom_tg := re.match(r'^([a-zA-Z0-9_]{4,})\.t\.me(?:/(.*))?$', clean, re.IGNORECASE):
        ch, path = custom_tg.group(1), custom_tg.group(2)
        return f"https://t.me/{ch}{'/' + path if path else ''}"
    if re.match(r'^(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/', clean, re.IGNORECASE):
        return f"https://{clean}"
    if not clean.startswith(("http://", "https://", "tg://")):
        if re.match(r'^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}', clean):
            return f"https://{clean}"
        return None
    return clean

def create_button(text: str, url: str, style=None) -> InlineKeyboardButton:
    if style is not None and COLORED_BUTTONS_SUPPORTED:
        try:
            return InlineKeyboardButton(text, url=url, style=style)
        except (TypeError, ValueError, AttributeError):
            try:
                style_val = getattr(style, "value", str(style).lower())
                return InlineKeyboardButton(text, url=url, style=style_val)
            except Exception:
                pass
    return InlineKeyboardButton(text, url=url)

BUTTON_REGEX = re.compile(r'\[([^\]]+)\](?:\s*[:\-–—|]?\s*\[?\(?([a-zA-Z]+)\)?\]?)?')

def parse_buttons(text: str, font_style: str = "sim", default_color=RED_STYLE) -> Optional[InlineKeyboardMarkup]:
    if not text:
        return None
    raw_lines = text.strip().splitlines()
    keyboard = []
    for line in raw_lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        row = []
        for content, out_color in BUTTON_REGEX.findall(line_clean):
            color_suffix = (out_color or "").strip().lower()
            match = URL_REGEX.search(content)
            if match:
                label = re.sub(r'[\s+|:–—\->]+$', '', content[:match.start()]).strip()
                raw_url = match.group(1).strip()
                in_color = re.sub(r'^[\s+|:–—\->]+', '', content[match.end():]).strip().lower()
            else:
                parts = re.split(r'\s+(?:\+|\->|\|)\s+', content)
                if len(parts) < 2:
                    continue
                label, raw_url = parts[0].strip(), parts[1].strip()
                in_color = parts[2].strip().lower() if len(parts) > 2 else ""
            if not label or not (clean_url := sanitize_button_url(raw_url)):
                continue
            btn_color = COLOR_MAP.get(in_color or color_suffix, default_color)
            styled_text = apply_font(label, font_style) if font_style != "normal" else label
            row.append(create_button(styled_text, clean_url, style=btn_color))
        if row:
            keyboard.append(row)
    return InlineKeyboardMarkup(keyboard) if keyboard else None

def parse_time_to_seconds(time_str: str) -> int:
    if not time_str:
        return 1
    if match := re.match(r'^(\d+)([smhd])$', time_str.strip().lower()):
        return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(match.group(2), 1)
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
    raw_num = cid_str.replace("-100", "").replace("-", "")
    queries = [{"chat_id": cid_str}]
    try:
        queries.append({"chat_id": int(cid_str)})
    except Exception:
        pass
    if raw_num.isdigit():
        queries.extend([
            {"chat_id": raw_num},
            {"chat_id": int(raw_num)},
            {"chat_id": f"-100{raw_num}"},
            {"chat_id": int(f"-100{raw_num}")}
        ])
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
    try:
        await authdb.update_many(
            {"$or": [{"admin_id": {"$exists": False}}, {"admin_id": None}, {"admin_id": ""}]},
            {"$set": {"admin_id": uid_str}}
        )
    except Exception:
        pass

async def get_button_template(user_id: int) -> Optional[Dict]:
    uid_str = str(user_id)
    return await btn_templatedb.find_one({"$or": [{"user_id": uid_str}, {"user_id": user_id}]})

async def get_effective_template(chat_id: int, username: Optional[str] = None) -> Optional[Dict]:
    settings = await get_channel_settings(chat_id, username)
    if settings and settings.get("admin_id"):
        if tmpl := await get_button_template(settings["admin_id"]):
            if tmpl.get("template"):
                return tmpl
    if global_tmpl := await btn_templatedb.find_one({"_id": "GLOBAL_ACTIVE_TEMPLATE"}):
        if global_tmpl.get("template"):
            return global_tmpl
    return await btn_templatedb.find_one(
        {"template": {"$exists": True, "$ne": ""}},
        sort=[("updated_at", -1), ("_id", -1)]
    )

async def delete_button_template(user_id: int):
    uid_str = str(user_id)
    await btn_templatedb.delete_many({"$or": [{"user_id": uid_str}, {"user_id": user_id}]})

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

TRIGGER_HTML_REGEX = re.compile(
    r'(?:^|\n|\s)[-–—•▪►👉🔗~]+\s*<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\'][^>]*>.*?</a>',
    re.IGNORECASE
)
TRIGGER_PLAIN_REGEX = re.compile(
    r'(?:^|\n|\s)[-–—•▪►👉🔗~]+\s*(https?://[^\s<>"\']+|tg://[^\s<>"\']+|t\.me/[^\s<>"\']+)',
    re.IGNORECASE
)

def extract_trigger_link_and_clean_caption(raw_text: str, html_text: str) -> Tuple[Optional[str], str, str]:
    if not raw_text and not html_text:
        return None, "", ""
    target_text = html_text or raw_text
    if m_html := TRIGGER_HTML_REGEX.search(target_text):
        url = m_html.group(1).strip()
        cl_html = TRIGGER_HTML_REGEX.sub('', target_text).strip()
        cl_raw = TRIGGER_HTML_REGEX.sub('', raw_text).strip() if raw_text else cl_html
        return url, cl_raw, cl_html
    if m_plain := TRIGGER_PLAIN_REGEX.search(target_text):
        url = m_plain.group(1).strip()
        cl_html = TRIGGER_PLAIN_REGEX.sub('', target_text).strip()
        cl_raw = TRIGGER_PLAIN_REGEX.sub('', raw_text).strip() if raw_text else cl_html
        return url, cl_raw, cl_html
    return None, raw_text, html_text

def apply_font_to_caption(caption: str, font_style: str) -> str:
    if not caption or font_style == "normal":
        return hyperlink_syntax_realm(caption)
    pattern = re.compile(r'(<[^>]+>|https?://[^\s]+|t\.me/[^\s]+|tg://[^\s]+)')
    lines = []
    for line in caption.split('\n'):
        lower_line = line.lower()
        if "syntaxrealm" in lower_line or "made by" in lower_line:
            lines.append(line)
            continue
        parts = pattern.split(line)
        styled = [p if (p.startswith('<') and p.endswith('>')) or p.startswith(('http', 't.me', 'tg://')) else apply_font(p, font_style) for p in parts if p]
        lines.append(''.join(styled))
    formatted_caption = '\n'.join(lines)
    return hyperlink_syntax_realm(formatted_caption)

def hyperlink_syntax_realm(text: str) -> str:
    if not text:
        return text
    if 'href="https://t.me/SyntaxRealm"' in text:
        return text
    credit_link = '<a href="https://t.me/SyntaxRealm">˹ 𝖲𝗒𝗇𝗍𝖺𝖷𝖱𝖾𝖺𝗅𝗆.𝗍.𝗆𝖾 ˼</a>'
    credit_pattern = re.compile(
        r"['\"`]?\s*(?:˹\s*)?SyntaxRealm(?:\.t\.me)?(?:\s*˼)?\s*['\"`]?",
        re.IGNORECASE
    )
    return credit_pattern.sub(credit_link, text)

async def safe_copy_and_delete(
    msg: Message,
    chat_id: int,
    caption: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> Optional[Message]:
    markup = reply_markup if reply_markup is not None else msg.reply_markup
    for _ in range(5):
        try:
            if msg.media:
                c = caption if caption is not None else (msg.caption or "")
                sent = await msg.copy(
                    chat_id,
                    caption=c,
                    parse_mode=ParseMode.HTML if caption else None,
                    reply_markup=markup
                )
            else:
                t = caption if caption is not None else (msg.text or "")
                sent = await app.send_message(
                    chat_id=chat_id,
                    text=t,
                    parse_mode=ParseMode.HTML if caption else None,
                    reply_markup=markup,
                    disable_web_page_preview=False
                )
            await asyncio.sleep(0.4)
            await msg.delete()
            return sent
        except Exception as e:
            if "FLOOD_WAIT" in str(e).upper():
                wait_match = re.search(r'(\d+)', str(e))
                wait_sec = int(wait_match.group(1)) + 2 if wait_match else 5
                await asyncio.sleep(wait_sec)
                continue
            logger.error(f"[AUTO-BUTTON] safe_copy_and_delete failed: {e}")
            break
    return None

def is_channel_chat(chat) -> bool:
    if not chat:
        return False
    chat_type = getattr(chat, "type", None)
    if chat_type is not None:
        try:
            if chat_type == ChatType.CHANNEL:
                return True
        except Exception:
            pass
        try:
            if hasattr(chat_type, "value") and str(chat_type.value).lower() == "channel":
                return True
        except Exception:
            pass
        type_str = str(chat_type).lower()
        if "channel" in type_str:
            return True
    chat_id = getattr(chat, "id", None)
    if chat_id is not None:
        try:
            cid = int(chat_id)
            if cid < 0 and str(cid).startswith("-100"):
                return True
        except Exception:
            pass
    return False

@app.on_message(filters.command(["testautobtn"]))
async def test_auto_btn_cmd(client, message: Message):
    chat = message.chat
    info = []
    info.append(f"🔍 **Auto Button Debug Info**")
    info.append(f"")
    info.append(f"📍 **Current Chat:**")
    info.append(f"  • ID: `{chat.id}`")
    info.append(f"  • Type: `{chat.type}`")
    info.append(f"  • Username: `@{chat.username}`")
    info.append(f"  • Is Channel: `{is_channel_chat(chat)}`")
    info.append(f"")
    settings = await get_channel_settings(chat.id, chat.username)
    if settings:
        info.append(f"✅ **Channel Authorized**")
        info.append(f"  • Forward Tag Removal: `{settings.get('forward_tag_removal')}`")
        info.append(f"  • Auto Accept Time: `{settings.get('auto_accept_time')}`")
        info.append(f"  • Admin ID: `{settings.get('admin_id')}`")
    else:
        info.append(f"❌ **Channel NOT Authorized**")
        info.append(f"  • Use `/auth` to authorize")
    info.append(f"")
    tmpl = await get_effective_template(chat.id, chat.username)
    if tmpl:
        info.append(f"✅ **Template Found**")
        info.append(f"  • Font: `{tmpl.get('font_style')}`")
        info.append(f"  • Template: `{tmpl.get('template')[:100]}`")
    else:
        info.append(f"❌ **No Template Set**")
        info.append(f"  • Use `/abset` to set template")
    await message.reply_text("\n".join(info))

async def _handle_channel_post(client, message: Message, source: str = "unknown"):
    try:
        # 🔒 CRITICAL: Check if message and chat exist
        if not message or not message.chat:
            return
        
        chat = message.chat
        chat_id = chat.id
        
        if not is_channel_chat(chat):
            return
        
        raw_text = message.caption or message.text or ""
        if not raw_text:
            return
        
        entities = message.caption_entities or message.entities
        html_text = get_html_text(raw_text, entities)
        extracted_url, cl_raw, cl_html = extract_trigger_link_and_clean_caption(raw_text, html_text)
        
        settings = await get_channel_settings(chat_id, chat.username)
        
        if not extracted_url:
            if settings and settings.get("forward_tag_removal") and is_forwarded_post(message):
                await safe_copy_and_delete(message, chat_id)
            return
        
        logger.info(f"[AUTO-BTN] Trigger link found: {extracted_url}")
        
        if not settings:
            settings = {
                "chat_id": str(chat_id),
                "forward_tag_removal": True,
                "auto_accept_time": "1s",
                "auto_accept_seconds": 1
            }
            asyncio.create_task(add_auth_channel(chat_id, forward_tag=True, auto_accept_time="1s"))
        
        tmpl_data = await get_effective_template(chat_id, chat.username)
        if not tmpl_data or not tmpl_data.get("template"):
            logger.warning(f"[AUTO-BTN] No template found for channel {chat_id}")
            return
        
        font_style = tmpl_data.get("font_style", "sim")
        btn_text = tmpl_data.get("template", "")
        btn_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", extracted_url, btn_text, flags=re.IGNORECASE)
        
        keyboard = parse_buttons(btn_text, font_style=font_style, default_color=RED_STYLE)
        if not keyboard:
            logger.warning(f"[AUTO-BTN] Failed to parse buttons")
            return
        
        final_caption = apply_font_to_caption(cl_html, font_style) if font_style != "normal" else cl_html
        raw_caption = apply_font_to_caption(cl_raw, font_style) if font_style != "normal" else cl_raw
        
        if settings.get("forward_tag_removal", True) and is_forwarded_post(message):
            await safe_copy_and_delete(message, chat_id, caption=final_caption, reply_markup=keyboard)
            return
        
        edit_success = False
        try:
            if message.media:
                await client.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message.id,
                    caption=final_caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            else:
                await client.edit_message_text(
                    text=final_caption,
                    chat_id=chat_id,
                    message_id=message.id,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            edit_success = True
        except Exception as err:
            err_str = str(err).upper()
            logger.warning(f"[AUTO-BTN] Edit failed: {err}")
            if "MESSAGE_NOT_MODIFIED" in err_str:
                try:
                    await client.edit_message_reply_markup(chat_id=chat_id, message_id=message.id, reply_markup=keyboard)
                    edit_success = True
                except Exception as e2:
                    logger.error(f"[AUTO-BTN] Reply markup update failed: {e2}")
            else:
                try:
                    if message.media:
                        await client.edit_message_caption(
                            chat_id=chat_id,
                            message_id=message.id,
                            caption=raw_caption,
                            parse_mode=None,
                            reply_markup=keyboard
                        )
                    else:
                        await client.edit_message_text(
                            text=raw_caption,
                            chat_id=chat_id,
                            message_id=message.id,
                            parse_mode=None,
                            reply_markup=keyboard
                        )
                    edit_success = True
                except Exception as e3:
                    logger.error(f"[AUTO-BTN] Fallback edit failed: {e3}")
        
        if not edit_success:
            await safe_copy_and_delete(message, chat_id, caption=final_caption, reply_markup=keyboard)
            
    except Exception as e:
        logger.error(f"[AUTO-BTN] Critical error: {e}", exc_info=True)

@app.on_message(filters.channel & ~filters.service)
async def channel_post_listener(client, message: Message):
    await _handle_channel_post(client, message, source="filters.channel")

@app.on_edited_message(filters.channel & ~filters.service)
async def channel_post_edit_listener(client, message: Message):
    await _handle_channel_post(client, message, source="edited.filters.channel")

try:
    from pyrogram.raw.types import UpdateNewChannelMessage, UpdateEditChannelMessage
    
    @app.on_raw_update()
    async def raw_channel_update_handler(client, update, users, chats):
        try:
            if isinstance(update, (UpdateNewChannelMessage, UpdateEditChannelMessage)):
                message = update.message
                channel_id = getattr(message, "peer_id", None)
                if channel_id:
                    channel_id = getattr(channel_id, "channel_id", None)
                    if channel_id:
                        full_id = int(f"-100{channel_id}")
                        try:
                            msg = await client.get_messages(full_id, message.id)
                            # 🔒 CRITICAL: Check if msg and msg.chat exist
                            if msg and msg.chat:
                                source = "raw_update_new" if isinstance(update, UpdateNewChannelMessage) else "raw_update_edit"
                                await _handle_channel_post(client, msg, source=source)
                        except Exception:
                            pass
        except Exception:
            pass
    
    logger.info("Raw update handler registered")
except Exception as e:
    logger.warning(f"Could not register raw update handler: {e}")

@app.on_chat_join_request()
async def auto_approve_join_request(client, request: ChatJoinRequest):
    try:
        if settings := await get_channel_settings(request.chat.id):
            await asyncio.sleep(settings.get("auto_accept_seconds", 1))
            await client.approve_chat_join_request(chat_id=request.chat.id, user_id=request.from_user.id)
    except Exception as e:
        logger.error(f"Auto-approve join request failed: {e}")

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
    try:
        chat_obj = await client.get_chat(chat_id)
        if not is_channel_chat(chat_obj):
            return await message.reply_text("❌ Ye sirf channels ke liye hai! Groups/supergroups ke liye kaam nahi karega.")
    except Exception as e:
        return await message.reply_text(f"❌ Channel verify nahi ho paya: {e}")
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
        if not data:
            return await message.reply_text("❌ Koi template set nahi hai! Pehle `/abset` karein.")
        preview_text = data["template"].replace("{link}", "https://t.me/PreviewDemo")
        preview_keyboard = parse_buttons(preview_text, font_style=data.get("font_style", "sim"), default_color=RED_STYLE)
        return await message.reply_text(
            f"📋 **Aapka Button Template:**\n`{data['template']}`\n\n🎨 **Font:** `{data.get('font_style', 'sim')}`\n👇 **Button Preview:**",
            reply_markup=preview_keyboard
        )
    if cmd == "abset":
        text = message.text or message.caption or ""
        font_style = "sim"
        if font_match := re.search(r"-f\s+(\w+)", text):
            font_style = font_match.group(1).lower()
        template_text = ""
        if message.reply_to_message and (message.reply_to_message.text or message.reply_to_message.caption):
            template_text = message.reply_to_message.text or message.reply_to_message.caption
        else:
            template_text = re.sub(r"^/abset\s*", "", text, flags=re.IGNORECASE)
            template_text = re.sub(r"-f\s+\w+", "", template_text, flags=re.IGNORECASE).strip()
        if not template_text:
            return await message.reply_text("❌ Template text provide karein! Format: `/abset [Text + {link}]`")
        test_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", "https://t.me/PreviewDemo", template_text, flags=re.IGNORECASE)
        test_keyboard = parse_buttons(test_text, font_style=font_style, default_color=RED_STYLE)
        if not test_keyboard:
            return await message.reply_text("❌ Koi valid button nahi mila! Please check your bracket format.")
        await save_button_template(user_id, template_text, font_style)
        return await message.reply_text(
            f"✅ **Button Template Set Ho Gaya!**\n🎨 **Font:** `{font_style}`\n🔴 **Default Color:** `Danger (Red)`\n👇 **Live Preview:**",
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
    if not template_data:
        return await message.reply_text("❌ Pehle `/abset` se template set karein!")
    template = template_data["template"]
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
                original_entities = []
        if not replacement_link and "{link}" in template.lower():
            return await message.reply_text("❌ Replacement link nahi mila! Link reply karein ya post me -link dalein.")
        btn_str = re.sub(r"\{\s*(?:link|url|target)\s*\}", replacement_link or "", template, flags=re.IGNORECASE)
        keyboard = parse_buttons(btn_str, font_style=font_style, default_color=RED_STYLE)
        if not keyboard:
            return await message.reply_text("❌ Buttons parse nahi ho paye.")
        formatted_caption = apply_font_to_caption(original_text, font_style) if font_style != "normal" else original_text
        try:
            if target_msg.media:
                await client.edit_message_caption(channel_id, msg_id, caption=formatted_caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
            else:
                await client.edit_message_text(text=formatted_caption, chat_id=channel_id, message_id=msg_id, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception as edit_err:
            if "MESSAGE_NOT_MODIFIED" in str(edit_err).upper():
                await client.edit_message_reply_markup(chat_id=channel_id, message_id=msg_id, reply_markup=keyboard)
            else:
                raise
        await message.reply_text("✅ **Buttons Successfully Attached!**")
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
        await client.edit_message_reply_markup(chat_id=channel_id, message_id=msg_id, reply_markup=keyboard)
        await message.reply_text("✅ Buttons updated successfully!")
    except Exception as e:
        await message.reply_text(f"⚠️ Update error: {e}")
