import re
import asyncio
import time
import logging
from typing import Dict, Optional, Tuple, List, Union
import pyrogram
from pyrogram import filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
)
from pyrogram.enums import ParseMode

logger = logging.getLogger("buttons")
logging.basicConfig(level=logging.INFO)

# -------------------- BUTTON STYLE ENUM & COLOR MAP -------------------- #
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
    # Red / Danger (Default)
    "r": RED_STYLE,
    "red": RED_STYLE,
    "danger": RED_STYLE,
    "d": RED_STYLE,
    # Green / Success
    "g": GREEN_STYLE,
    "green": GREEN_STYLE,
    "success": GREEN_STYLE,
    "s": GREEN_STYLE,
    # Blue / Primary
    "b": BLUE_STYLE,
    "blue": BLUE_STYLE,
    "primary": BLUE_STYLE,
    "p": BLUE_STYLE,
    # Normal / Unstyled
    "none": None,
    "normal": None,
    "default": None,
    "off": None,
}

from DURGESH import app
from DURGESH.database import db

authdb = db.auth_channels
btn_templatedb = db.button_templates

# -------------------- FONT STYLES & NORMALIZER -------------------- #
FONT_S_KEYS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
FONT_S_VALS = 'ᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢ'
FONT_S = dict(zip(FONT_S_KEYS, FONT_S_VALS))

FONT_SM_KEYS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
FONT_SM_VALS = 'ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿'
FONT_SM = dict(zip(FONT_SM_KEYS, FONT_SM_VALS))

STYLE_SIM_KEYS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
STYLE_SIM_VALS = '𝖠𝖡𝖢𝖣𝖤𝖥𝖦𝖧𝖨𝖩𝖪𝖫𝖬𝖭𝖮𝖯𝖰𝖱𝖲𝖳𝖴𝖵𝖶𝖷𝖸𝖹𝖺𝖻𝖼𝖽𝖾𝖿𝗀𝗁𝗂𝗃𝗄𝗅𝗆𝗇𝗈𝗉𝗊𝗋𝗌𝗍𝗎𝗏𝗐𝗑𝗒𝗓'
STYLE_SIM = dict(zip(STYLE_SIM_KEYS, STYLE_SIM_VALS))

STYLE_SAN_KEYS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
STYLE_SAN_VALS = '𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵'
STYLE_SAN = dict(zip(STYLE_SAN_KEYS, STYLE_SAN_VALS))

# REVERSE MAP: Converts any custom styled text back to normal A-Z / 0-9
REVERSE_MAP = {}
for k, v in zip(FONT_S_KEYS, FONT_S_VALS):
    if v not in REVERSE_MAP: REVERSE_MAP[v] = k
for k, v in zip(FONT_SM_KEYS, FONT_SM_VALS):
    if v not in REVERSE_MAP: REVERSE_MAP[v] = k
for k, v in zip(STYLE_SIM_KEYS, STYLE_SIM_VALS):
    if v not in REVERSE_MAP: REVERSE_MAP[v] = k
for k, v in zip(STYLE_SAN_KEYS, STYLE_SAN_VALS):
    if v not in REVERSE_MAP: REVERSE_MAP[v] = k

def apply_font(text: str, font_style: str) -> str:
    """Un-styles text using REVERSE_MAP, then applies the requested font style."""
    normalized_text = ''.join(REVERSE_MAP.get(c, c) for c in text)
    if font_style == 's': return ''.join(FONT_S.get(c, c) for c in normalized_text)
    elif font_style == 'sm': return ''.join(FONT_SM.get(c, c) for c in normalized_text)
    elif font_style in ['sim', 'a']: return ''.join(STYLE_SIM.get(c, c) for c in normalized_text)
    elif font_style in ['san', 'b']: return ''.join(STYLE_SAN.get(c, c) for c in normalized_text)
    return normalized_text

# -------------------- URL SANITIZER & VALIDATOR -------------------- #
def sanitize_button_url(url: str) -> Optional[str]:
    """
    Cleans and standardizes button URLs to prevent [400 BUTTON_URL_INVALID]:
    - Strips quotes, brackets, and invisible Unicode whitespace.
    - Converts @usernames to https://t.me/usernames.
    - Converts t.me/ and .t.me short-links to full https:// URLs.
    - Validates scheme (http://, https://, tg://).
    """
    if not url:
        return None
    # Strip quotes, angle brackets, and backticks
    clean = url.strip().strip("'\"<>`").strip()
    # Remove zero-width spaces and invisible characters
    clean = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\u00a0\r\n]+', '', clean).strip()

    # Reject unreplaced placeholders
    if re.match(r'^\{.*\}$', clean):
        return None

    # Handle @username -> https://t.me/username
    if clean.startswith("@"):
        return f"https://t.me/{clean.lstrip('@')}"

    # Handle custom domain shortlink: Name.t.me -> https://t.me/Name
    custom_tg = re.match(r'^([a-zA-Z0-9_]{4,})\.t\.me(?:/(.*))?$', clean, re.IGNORECASE)
    if custom_tg:
        ch = custom_tg.group(1)
        path = custom_tg.group(2)
        return f"https://t.me/{ch}{'/' + path if path else ''}"

    # Handle t.me/ or telegram.me/ without https://
    if re.match(r'^(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/', clean, re.IGNORECASE):
        return f"https://{clean}"

    # Handle standard web URLs without scheme: www.example.com or domain.com
    if not clean.startswith(("http://", "https://", "tg://")):
        if re.match(r'^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}', clean):
            return f"https://{clean}"
        return None

    return clean

# -------------------- DB HELPERS & TIME PARSER -------------------- #
def parse_time_to_seconds(time_str: str) -> int:
    if not time_str: return 1
    match = re.match(r'^(\d+)([smhd])$', time_str.strip().lower())
    if not match: return 1
    return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(match.group(2), 1)

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
    # Upsert matching both string and integer chat_id formats
    await authdb.update_one(
        {"$or": [{"chat_id": cid_str}, {"chat_id": chat_id}]}, 
        {"$set": payload}, 
        upsert=True
    )

async def remove_auth_channel(chat_id: int):
    cid_str = str(chat_id)
    await authdb.delete_many({"$or": [{"chat_id": cid_str}, {"chat_id": chat_id}]})

async def get_channel_settings(chat_id: int, username: Optional[str] = None) -> Optional[Dict]:
    """Robust lookup that supports string, integer, +/-100 prefix, and username variations."""
    cid_str = str(chat_id)
    queries = [{"chat_id": cid_str}]
    try:
        queries.append({"chat_id": int(cid_str)})
    except Exception:
        pass

    raw_num = cid_str.replace("-100", "").replace("-", "")
    if raw_num.isdigit():
        queries.extend([
            {"chat_id": raw_num},
            {"chat_id": int(raw_num)},
            {"chat_id": f"-100{raw_num}"},
            {"chat_id": int(f"-100{raw_num}")},
            {"chat_id": f"-{raw_num}"},
            {"chat_id": int(f"-{raw_num}")}
        ])

    if username:
        clean_user = username.lstrip("@").lower()
        queries.extend([
            {"chat_id": f"@{clean_user}"},
            {"chat_id": clean_user}
        ])

    data = await authdb.find_one({"$or": queries})
    if data:
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
    """
    Saves the button template for the specific admin AND updates the active global template
    so automatic channel posting always gets the latest colors and styles.
    """
    uid_str = str(user_id)
    now = time.time()
    
    # 1. Update user specific template
    await btn_templatedb.update_one(
        {"$or": [{"user_id": uid_str}, {"user_id": user_id}]}, 
        {"$set": {
            "user_id": uid_str, 
            "template": template, 
            "font_style": font_style,
            "updated_at": now
        }}, 
        upsert=True
    )
    
    # 2. Update global active template reference (guarantees auto-buttons pick latest color format)
    await btn_templatedb.update_one(
        {"_id": "GLOBAL_ACTIVE_TEMPLATE"},
        {"$set": {
            "template": template,
            "font_style": font_style,
            "user_id": uid_str,
            "updated_at": now
        }},
        upsert=True
    )
    
    # 3. Synchronize authorized channels to link with this active admin
    try:
        await authdb.update_many(
            {}, 
            {"$set": {"admin_id": uid_str}}
        )
    except Exception as e:
        logger.warning(f"[TEMPLATE-SYNC] Error updating channel admin_id: {e}")

async def get_button_template(user_id: Union[int, str]) -> Optional[Dict]:
    uid_str = str(user_id)
    tmpl = await btn_templatedb.find_one({"$or": [{"user_id": uid_str}, {"user_id": int(uid_str) if uid_str.isdigit() else uid_str}]})
    if tmpl and tmpl.get("template"):
        return tmpl
    # Fallback to global active template
    return await btn_templatedb.find_one({"_id": "GLOBAL_ACTIVE_TEMPLATE"})

async def get_effective_template(chat_id: int, username: Optional[str] = None) -> Optional[Dict]:
    """
    Finds the active button template:
    1. Channel specific admin template if set.
    2. Global active template updated via /abset.
    3. Most recently updated template across all users in DB.
    """
    global_tmpl = await btn_templatedb.find_one({"_id": "GLOBAL_ACTIVE_TEMPLATE"})
    
    settings = await get_channel_settings(chat_id, username)
    admin_tmpl = None
    if settings and settings.get("admin_id"):
        admin_tmpl = await get_button_template(settings["admin_id"])
        
    latest_tmpl = await btn_templatedb.find_one(
        {"template": {"$exists": True, "$ne": ""}}, 
        sort=[("updated_at", -1), ("_id", -1)]
    )
    
    candidates = [t for t in [global_tmpl, admin_tmpl, latest_tmpl] if t and t.get("template")]
    if not candidates:
        return None
    # Prioritize candidate with the most recent updated_at timestamp
    candidates.sort(key=lambda x: x.get("updated_at", 0), reverse=True)
    return candidates[0]

async def delete_button_template(user_id: int):
    uid_str = str(user_id)
    await btn_templatedb.delete_many({"$or": [{"user_id": uid_str}, {"user_id": user_id}]})
    # Reset global active if it was created by this user
    await btn_templatedb.delete_many({"_id": "GLOBAL_ACTIVE_TEMPLATE", "user_id": uid_str})

# -------------------- LINK & ID EXTRACTORS -------------------- #
def get_forward_chat(msg: Optional[Message]):
    """Safely retrieves the forwarded chat object without triggering deprecation warnings."""
    if not msg:
        return None
    origin = getattr(msg, "forward_origin", None)
    if origin:
        if hasattr(origin, "chat") and getattr(origin.chat, "sender_chat", None):
            return origin.chat.sender_chat
        chat_obj = getattr(origin, "sender_chat", None) or getattr(origin.chat if hasattr(origin, "chat") else None, "sender_chat", None) or getattr(origin, "chat", None)
        if chat_obj:
            return getattr(chat_obj, "sender_chat", chat_obj)
            
    if not hasattr(msg, "forward_origin"):
        try:
            return getattr(msg, "forward_from_chat", None)
        except Exception:
            return None
    return None

def extract_chat_and_msg_id(link: str) -> Tuple[Optional[int], Optional[int]]:
    """Accurately extracts channel/chat ID and message ID from Telegram links."""
    link = link.strip()
    pub = re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", link)
    if pub:
        return None, None
    priv = re.match(r"https?://t\.me/c/(-?\d+)/(\d+)", link)
    if priv:
        raw_id = priv.group(1).lstrip("-")
        chat_id = int(f"-{raw_id}") if raw_id.startswith("100") else int(f"-100{raw_id}")
        return chat_id, int(priv.group(2))
    return None, None

def create_button(text: str, url: str, style=RED_STYLE) -> InlineKeyboardButton:
    """Creates an InlineKeyboardButton defaulting to Red (danger) across all Pyrogram/Pyrofork forks."""
    if style in ["none", "normal", "default", "off"]:
        style = None

    if style is not None:
        # 1. Try passing the style enum directly
        try:
            return InlineKeyboardButton(text, url=url, style=style)
        except Exception:
            pass
        # 2. Try passing style value/string (e.g. 'danger', 'success', 'primary')
        try:
            style_val = getattr(style, "value", str(style)).lower()
            return InlineKeyboardButton(text, url=url, style=style_val)
        except Exception:
            pass
        # 3. Fallback for forks using 'color' attribute
        try:
            return InlineKeyboardButton(text, url=url, color=style)
        except Exception:
            pass
        # 4. Attach attribute directly if supported
        try:
            btn = InlineKeyboardButton(text, url=url)
            style_val = getattr(style, "value", str(style)).lower()
            try:
                setattr(btn, "style", style_val)
            except Exception:
                pass
            return btn
        except Exception:
            pass
    return InlineKeyboardButton(text, url=url)

# Regex to detect URLs, placeholders, @handles, or domain links without splitting on '+' in button labels
URL_OR_PLACEHOLDER_REGEX = re.compile(
    r'(\{\s*(?:link|url|target)\s*\}|https?://[^\s<>"\']+|tg://[^\s<>"\']+|t\.me/[^\s<>"\']+|@[a-zA-Z0-9_]{4,}|(?:[a-zA-Z0-9_\-]+\.)+[a-zA-Z]{2,}/[^\s<>"\']*)',
    re.IGNORECASE
)

def parse_buttons(text: str, font_style: str = "sim", default_color=RED_STYLE) -> Optional[InlineKeyboardMarkup]:
    """
    Versatile parser that:
    1. Preserves button names with '+' (e.g. '18+ Zone', 'Disney+', 'C++') without breaking URL splitting.
    2. Defaults every button to RED (Danger) style unless another color is explicitly provided.
    3. Handles both single-row and multi-row templates cleanly (including compact ][ formatting).
    """
    if not text:
        return None

    # Convert compact '][' without space to newline so each button stays on its own row
    text = re.sub(r'\]\[', ']\n[', text)

    keyboard = []

    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        btns = []

        # Matches [Content] with optional trailing color indicator outside brackets
        raw_matches = re.findall(
            r'\[([^\]]+)\](?:\s*(?:[:\-–—|]|\b)\s*(?:\[([a-zA-Z]+)\]|\(([a-zA-Z]+)\)|([a-zA-Z]+)))?', 
            line
        )

        for match in raw_matches:
            content = match[0].strip()
            outside_color = (match[1] or match[2] or match[3] or "").strip().lower()

            label = ""
            raw_link = ""
            inside_color = ""

            # Step 1: Detect URL / placeholder position inside content to avoid breaking titles with '+' like '18+ Zone'
            url_match = URL_OR_PLACEHOLDER_REGEX.search(content)
            if url_match:
                start_pos = url_match.start()
                end_pos = url_match.end()

                raw_link = url_match.group(1).strip()

                # Label is everything before the URL match minus the trailing separator (+, |, ->, :)
                before_str = content[:start_pos].strip()
                label = re.sub(r'[\s+|:–—\->]+$', '', before_str).strip()

                # Inside color is anything after the URL match minus leading separator
                after_str = content[end_pos:].strip()
                if after_str:
                    inside_color = re.sub(r'^[\s+|:–—\->]+', '', after_str).strip().lower()
            else:
                # Fallback: Split requiring spaces around separator to avoid breaking '18+'
                parts = re.split(r'\s+(?:\+|\->|\|)\s+', content)
                if len(parts) >= 2:
                    label = parts[0].strip()
                    raw_link = parts[1].strip()
                    if len(parts) >= 3:
                        inside_color = parts[2].strip().lower()
                else:
                    continue

            if not label or not raw_link:
                continue

            clean_link = sanitize_button_url(raw_link)
            if not clean_link:
                logger.warning(f"[AUTO-BUTTON] Skipping button with invalid URL: '{raw_link}' (Label: '{label}')")
                continue

            # Determine button color style: inside bracket > outside bracket > default red
            chosen_color_str = inside_color or outside_color
            if chosen_color_str:
                btn_style = COLOR_MAP.get(chosen_color_str, RED_STYLE)
            else:
                btn_style = default_color  # DEFAULT IS RED!

            styled_label = apply_font(label, font_style) if font_style != "normal" else label
            btns.append(create_button(styled_label, clean_link, style=btn_style))

        if btns:
            keyboard.append(btns)

    return InlineKeyboardMarkup(keyboard) if keyboard else None

# -------------------- ADVANCED ENTITY TO HTML CONVERTER -------------------- #
def get_html_text(text: str, entities: list) -> str:
    if not text: return ""
    if not entities: return text
    
    try: 
        text_16 = text.encode('utf-16-le')
    except Exception: 
        return text
        
    events = {}
    for i, e in enumerate(entities):
        start = e.offset * 2
        end = (e.offset + e.length) * 2
        start_tag, end_tag = "", ""
        
        type_str = getattr(e.type, "value", str(e.type)).lower()
        if "bold" in type_str:
            start_tag, end_tag = "<b>", "</b>"
        elif "italic" in type_str:
            start_tag, end_tag = "<i>", "</i>"
        elif "code" in type_str:
            start_tag, end_tag = "<code>", "</code>"
        elif "pre" in type_str:
            lang = getattr(e, "language", "") or ""
            start_tag, end_tag = f'<pre><code class="language-{lang}">', "</code></pre>"
        elif "text_link" in type_str and getattr(e, "url", None):
            start_tag, end_tag = f'<a href="{e.url}">', "</a>"
        elif "text_mention" in type_str and getattr(e, "user", None):
            start_tag, end_tag = f'<a href="tg://user?id={e.user.id}">', "</a>"
        elif "strikethrough" in type_str:
            start_tag, end_tag = "<s>", "</s>"
        elif "underline" in type_str:
            start_tag, end_tag = "<u>", "</u>"
        elif "spoiler" in type_str:
            start_tag, end_tag = "<spoiler>", "</spoiler>"
        elif "blockquote" in type_str:
            start_tag, end_tag = "<blockquote>", "</blockquote>"

        if start_tag:
            if start not in events: events[start] = []
            if end not in events: events[end] = []
            events[start].append(('start', i, start_tag))
            events[end].append(('end', i, end_tag))
            
    res = ""
    last_idx = 0
    for idx in sorted(events.keys()):
        res += text_16[last_idx:idx].decode('utf-16-le')
        evs = events[idx]
        ends = [e for e in evs if e[0] == 'end']
        starts = [e for e in evs if e[0] == 'start']
        
        ends.sort(key=lambda x: x[1], reverse=True)
        starts.sort(key=lambda x: x[1])
        
        for e in ends: res += e[2]
        for e in starts: res += e[2]
        last_idx = idx
        
    res += text_16[last_idx:].decode('utf-16-le')
    return res

# -------------------- CAPTION FONT UPDATER & LINK CLEANER -------------------- #
def extract_trigger_link_and_clean_caption(raw_text: str, html_text: str) -> Tuple[Optional[str], str, str]:
    """
    Detects trigger links:
    1. Prefixed by -, –, —, ~, •, 👉, 🔗, > (e.g. -https://... or - https://...)
    2. Hyperlinked HTML tag: -<a href="...">...</a>
    3. Standalone URLs on their own line or at the bottom of the caption
    Returns: (extracted_url, cleaned_raw_text, cleaned_html_text)
    """
    if not raw_text and not html_text:
        return None, "", ""

    target_text = html_text or raw_text

    # Pattern 1: Hyperlinked HTML tag with trigger prefix: -<a href="...">...</a>
    html_pattern = re.compile(
        r'(?:^|\n|\s)[-–—~•👉🔗>]\s*<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\'][^>]*>.*?</a>',
        re.IGNORECASE
    )
    match_html = html_pattern.search(target_text)
    if match_html:
        extracted_url = match_html.group(1).strip()
        cleaned_html = html_pattern.sub('', target_text).strip()
        cleaned_raw = html_pattern.sub('', raw_text).strip() if raw_text else cleaned_html
        return sanitize_button_url(extracted_url), re.sub(r'\n{3,}', '\n\n', cleaned_raw).strip(), re.sub(r'\n{3,}', '\n\n', cleaned_html).strip()

    # Pattern 2: Standard prefixed link: -https://... or 👉 https://...
    prefix_pattern = re.compile(
        r'(?:^|\n|\s)[-–—~•👉🔗>]\s*(https?://[^\s<>"\']+|t\.me/[^\s<>"\']+)',
        re.IGNORECASE
    )
    match_prefix = prefix_pattern.search(target_text)
    if match_prefix:
        extracted_url = match_prefix.group(1).strip()
        cleaned_html = prefix_pattern.sub('', target_text).strip()
        cleaned_raw = prefix_pattern.sub('', raw_text).strip() if raw_text else cleaned_html
        return sanitize_button_url(extracted_url), re.sub(r'\n{3,}', '\n\n', cleaned_raw).strip(), re.sub(r'\n{3,}', '\n\n', cleaned_html).strip()

    # Pattern 3: Standalone URL on its own line (without prefix)
    standalone_line_pattern = re.compile(
        r'(?:^|\n)\s*(https?://[^\s<>"\']+|t\.me/[^\s<>"\']+)\s*(?:\n|$)',
        re.IGNORECASE
    )
    match_standalone = standalone_line_pattern.search(target_text)
    if match_standalone:
        extracted_url = match_standalone.group(1).strip()
        cleaned_html = standalone_line_pattern.sub('\n', target_text).strip()
        cleaned_raw = standalone_line_pattern.sub('\n', raw_text).strip() if raw_text else cleaned_html
        return sanitize_button_url(extracted_url), re.sub(r'\n{3,}', '\n\n', cleaned_raw).strip(), re.sub(r'\n{3,}', '\n\n', cleaned_html).strip()

    # Pattern 4: Fallback - any URL present in text
    any_url_pattern = re.compile(
        r'(https?://[^\s<>"\']+|t\.me/[^\s<>"\']+)',
        re.IGNORECASE
    )
    match_any = any_url_pattern.search(target_text)
    if match_any:
        extracted_url = match_any.group(1).strip()
        cleaned_html = any_url_pattern.sub('', target_text).strip()
        cleaned_raw = any_url_pattern.sub('', raw_text).strip() if raw_text else cleaned_html
        return sanitize_button_url(extracted_url), re.sub(r'\n{3,}', '\n\n', cleaned_raw).strip(), re.sub(r'\n{3,}', '\n\n', cleaned_html).strip()

    return None, raw_text, html_text

def apply_font_to_caption(caption: str, font_style: str) -> str:
    if not caption or font_style == "normal": 
        return caption
    
    lines = caption.split('\n')
    new_lines = []
    pattern = re.compile(r'(<[^>]+>|https?://[^\s]+|t\.me/[^\s]+|tg://[^\s]+)')
    
    for line in lines:
        lower_line = line.lower()
        if "syntaxrealm.t.me" in lower_line or "❖" in line or "made by" in lower_line:
            new_lines.append(line)
            continue
            
        parts = pattern.split(line)
        styled_parts = []
        for part in parts:
            if not part: continue
            if part.startswith('<') and part.endswith('>'):
                styled_parts.append(part)
            elif part.startswith('http') or part.startswith('t.me') or part.startswith('tg://'):
                styled_parts.append(part)
            else:
                styled_parts.append(apply_font(part, font_style))
        new_lines.append(''.join(styled_parts))
        
    return '\n'.join(new_lines)

# -------------------- AUTH COMMANDS -------------------- #
@app.on_message(filters.command(["auth"]))
async def auth_channel_cmd(client, message: Message):
    args = message.text.split()
    forward_tag, auto_accept_time, chat_id = True, "1s", None
    if "-f" in args and args.index("-f") + 1 < len(args): 
        forward_tag = args[args.index("-f") + 1].lower() in ["on", "true", "1"]
    if "-ac" in args and args.index("-ac") + 1 < len(args): 
        auto_accept_time = args[args.index("-ac") + 1]
    
    fwd_chat = get_forward_chat(message.reply_to_message)
    if fwd_chat: 
        chat_id = fwd_chat.id
    elif len(args) >= 2:
        try: 
            chat_id = (await client.get_chat(args[1])).id if args[1].startswith("@") else int(args[1])
        except Exception as e: 
            return await message.reply_text(f"❌ Invalid channel! Error: {e}")
            
    if not chat_id: 
        return await message.reply_text("❌ Usage: `/auth <channel_id> -f on/off -ac 1s`")
    
    try:
        priv = getattr(await client.get_chat_member(chat_id, "me"), "privileges", None)
        if not priv or not getattr(priv, "can_post_messages", False): 
            return await message.reply_text("❌ Bot needs post messages rights in target channel.")
    except Exception as e: 
        return await message.reply_text(f"⚠️ Error checking rights: {e}")
    
    admin_id = message.from_user.id if message.from_user else None
    await add_auth_channel(chat_id, forward_tag, auto_accept_time, admin_id=admin_id)
    await message.reply_text(
        f"✅ **Channel Authorized!**\n"
        f"🆔 ID: `{chat_id}`\n"
        f"🔄 Forward Tag Removal: `{'ON' if forward_tag else 'OFF'}`\n"
        f"⏱ Auto-Accept: `{auto_accept_time}`"
    )

@app.on_message(filters.command(["unauth"]))
async def unauth_channel_cmd(client, message: Message):
    chat_id = None
    if len(message.command) == 2:
        try: 
            chat_id = (await client.get_chat(message.command[1])).id if message.command[1].startswith("@") else int(message.command[1])
        except Exception: 
            return await message.reply_text("❌ Invalid channel!")
    else:
        fwd_chat = get_forward_chat(message.reply_to_message)
        if fwd_chat: 
            chat_id = fwd_chat.id
        else: 
            return await message.reply_text("❌ Usage: `/unauth <channel_id>`")
        
    await remove_auth_channel(chat_id)
    await message.reply_text(f"✅ Un-Authorized: `{chat_id}`")

# -------------------- MASTER AUTO BUTTON HANDLER -------------------- #
@app.on_message(filters.command(["ab", "abset", "absee", "abseen", "abrm"]))
async def auto_button_handler(client, message: Message):
    cmd = message.command[0].lower()
    args = message.command[1:]
    
    if cmd == "abrm":
        await delete_button_template(message.from_user.id)
        return await message.reply_text("🗑️ Template remove kar diya gaya hai!")

    if cmd in ["absee", "abseen"]:
        data = await get_button_template(message.from_user.id)
        if not data: 
            return await message.reply_text("❌ Koi template set nahi hai! Pehle `/abset` karein.")
        template_text, font_style = data["template"], data.get("font_style", "sim")
        preview_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", "https://t.me/PreviewDemo", template_text, flags=re.IGNORECASE)
        preview_keyboard = parse_buttons(preview_text, font_style=font_style)
        font_display = {"sim": "Sim (Serif)", "san": "San (Bold)", "s": "Small Caps", "sm": "Small+Num", "normal": "Default"}
        return await message.reply_text(
            f"📋 **Aapka Button Template:**\n`{template_text}`\n\n"
            f"🔴 **Default Button Color:** `Red (Danger)`\n"
            f"🎨 **Font:** `{font_display.get(font_style, font_style)}`\n"
            f"👇 **Button Preview (Color & Format):**",
            reply_markup=preview_keyboard
        )

    if cmd == "abset" or (cmd == "ab" and "-s" in message.text.lower()):
        font_style = "sim"
        text = message.text or message.caption or ""
        font_match = re.search(r"-f\s+(\w+)", text)
        if font_match:
            font_style = font_match.group(1).lower()
            if font_style not in ["sim", "san", "s", "sm", "normal"]: 
                font_style = "sim"
                
        template_text = ""
        if message.reply_to_message and (message.reply_to_message.text or message.reply_to_message.caption):
            template_text = message.reply_to_message.text or message.reply_to_message.caption
        else:
            template_text = re.sub(r"^/(ab|abset)\s*", "", text, flags=re.IGNORECASE)
            template_text = re.sub(r"-s", "", template_text, flags=re.IGNORECASE)
            template_text = re.sub(r"-f\s+\w+", "", template_text, flags=re.IGNORECASE).strip()
            
        if not template_text: 
            return await message.reply_text("❌ Template text provide karein! Message ko reply karke `/abset` karein.")
            
        # Test parse replacing all {link}/{url} variations with dummy URL
        test_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", "https://t.me/PreviewDemo", template_text, flags=re.IGNORECASE)
        test_keyboard = parse_buttons(test_text, font_style=font_style)
        if not test_keyboard: 
            return await message.reply_text("❌ Koi valid button nahi mila! Format: `[Text + {link}]`")
            
        await save_button_template(message.from_user.id, template_text, font_style)
        
        font_display = {"sim": "Sim (Serif)", "san": "San (Bold)", "s": "Small Caps", "sm": "Small+Num", "normal": "Default"}
        return await message.reply_text(
            f"✅ **Button Template Set Ho Gaya!**\n"
            f"🔴 **Default Button Color:** `Red (Danger)`\n"
            f"🎨 **Font:** `{font_display.get(font_style, font_style)}`\n"
            f"👇 **Live Preview (4 Buttons in Red):**",
            reply_markup=test_keyboard
        )

    if cmd == "ab":
        if not args:
            return await message.reply_text(
                "❌ **Usage Guide:**\n"
                "1️⃣ **Set Template:** `/abset` (reply to template text)\n"
                "2️⃣ **Apply Template:** `/ab <target_post_link>` (reply to link message, or post contains -https... link)"
            )
            
        target_link = args[0]
        replacement_link = None
        
        if message.reply_to_message:
            replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
            url_match = re.search(r"(https?://\S+)", replied_text)
            if url_match: 
                replacement_link = url_match.group(1)
            
        channel_id, msg_id = extract_chat_and_msg_id(target_link)
        if not channel_id:
            pub_match = re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", target_link)
            if pub_match:
                try: 
                    channel_id, msg_id = (await client.get_chat(pub_match.group(1))).id, int(pub_match.group(2))
                except Exception as e: 
                    return await message.reply_text(f"❌ Channel nahi mila: {e}")
            else:
                return await message.reply_text("❌ Invalid target link format!")
            
        if not await is_channel_authed(channel_id): 
            return await message.reply_text("❌ Channel authorized nahi hai.")

        # Always fetch effective template with newest colors
        template_data = await get_effective_template(channel_id)
        if not template_data: 
            template_data = await get_button_template(message.from_user.id)
            if not template_data:
                return await message.reply_text("❌ Pehle `/abset` se template set karein!")
            
        template, font_style = template_data["template"], template_data.get("font_style", "sim")
                
        try:
            target_msg = await client.get_messages(channel_id, msg_id)
            original_text = target_msg.caption or target_msg.text or ""
            original_entities = target_msg.caption_entities or target_msg.entities

            # If no replied link, check if target message contains a -https trigger link
            if not replacement_link:
                html_text = get_html_text(original_text, original_entities)
                ext_url, cl_raw, cl_html = extract_trigger_link_and_clean_caption(original_text, html_text)
                if ext_url:
                    replacement_link = ext_url
                    original_text = cl_raw
                    original_entities = []

            if not replacement_link:
                return await message.reply_text("❌ Replacement link wale message ko reply karein!")

            final_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", replacement_link, template, flags=re.IGNORECASE)
            keyboard = parse_buttons(final_text, font_style=font_style)
            if not keyboard: 
                return await message.reply_text("❌ Buttons parse nahi ho paye.")

            if original_text:
                html_text = get_html_text(original_text, original_entities) if original_entities else original_text
                new_text = apply_font_to_caption(html_text, font_style) if font_style != "normal" else html_text
                
                try:
                    if target_msg.media:
                        await client.edit_message_caption(
                            chat_id=channel_id, 
                            message_id=msg_id, 
                            caption=new_text,
                            parse_mode=ParseMode.HTML, 
                            reply_markup=keyboard 
                        )
                    else:
                        await client.edit_message_text(
                            chat_id=channel_id, 
                            message_id=msg_id, 
                            text=new_text,
                            parse_mode=ParseMode.HTML, 
                            reply_markup=keyboard
                        )
                    # Re-enforce reply markup to ensure button color rendering
                    try:
                        await client.edit_message_reply_markup(chat_id=channel_id, message_id=msg_id, reply_markup=keyboard)
                    except Exception:
                        pass
                    await message.reply_text("✅ **Buttons & Font Successfully Applied!**")
                except Exception as edit_err:
                    if "MESSAGE_NOT_MODIFIED" in str(edit_err).upper():
                        try:
                            await client.edit_message_reply_markup(chat_id=channel_id, message_id=msg_id, reply_markup=keyboard)
                            await message.reply_text("✅ **Buttons Updated / Re-applied!**")
                        except Exception as e2:
                            if "MESSAGE_NOT_MODIFIED" in str(e2).upper():
                                await message.reply_text("ℹ️ **Post & Buttons pehle se updated hain!**")
                            else:
                                await message.reply_text(f"⚠️ Reply markup error: {e2}")
                    else:
                        await message.reply_text(f"⚠️ Edit fail: {edit_err}")
            else:
                try:
                    await client.edit_message_reply_markup(chat_id=channel_id, message_id=msg_id, reply_markup=keyboard)
                    await message.reply_text("✅ **Buttons Set!**")
                except Exception as err:
                    if "MESSAGE_NOT_MODIFIED" in str(err).upper():
                        await message.reply_text("ℹ️ **Buttons pehle se set hain!**")
                    else:
                        await message.reply_text(f"⚠️ Edit fail: {err}")
                
        except Exception as e: 
            await message.reply_text(f"⚠️ Operation fail: {e}")

# -------------------- CHANGE BUTTON (/cb) -------------------- #
@app.on_message(filters.command(["cb"]))
async def change_button_with_link(client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.text: 
        return await message.reply_text("❌ Reply to a button-text message with `/cb <post_link>`")
    args = message.command
    if len(args) < 2: 
        return await message.reply_text("❌ Usage: `/cb <post_link>`")
    
    link = args[1]
    channel_id, msg_id = extract_chat_and_msg_id(link)
    if not channel_id:
        pub_match = re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", link)
        if pub_match:
            try: 
                channel_id, msg_id = (await client.get_chat(pub_match.group(1))).id, int(pub_match.group(2))
            except Exception as e: 
                return await message.reply_text(f"❌ Channel nahi mila: {e}")
        else:
            return await message.reply_text("❌ Invalid link format!")
    
    if not await is_channel_authed(channel_id): 
        return await message.reply_text("❌ Channel authorized nahi hai.")
    
    keyboard = parse_buttons(message.reply_to_message.text, font_style="normal")
    if not keyboard: 
        return await message.reply_text("❌ Invalid button format!")
    
    try:
        await client.edit_message_reply_markup(chat_id=channel_id, message_id=msg_id, reply_markup=keyboard)
        await message.reply_text("✅ Buttons updated!")
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" in str(e).upper():
            await message.reply_text("ℹ️ **Same buttons already present!**")
        else:
            await message.reply_text(f"⚠️ Edit fail: {e}")

# -------------------- FORWARD TAG REMOVER & AUTO APPROVE -------------------- #
def is_forwarded(message: Message) -> bool:
    """Checks if a message is forwarded without deprecation warnings."""
    if hasattr(message, "forward_origin"):
        return message.forward_origin is not None
    try:
        return bool(
            getattr(message, "forward_date", None) or
            getattr(message, "forward_from_chat", None) or
            getattr(message, "forward_from", None)
        )
    except Exception:
        return False

async def safe_copy_and_delete(
    msg: Message, 
    chat_id: int, 
    custom_caption: Optional[str] = None, 
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    parse_mode: Optional[ParseMode] = ParseMode.HTML
) -> Optional[Message]:
    """Clones the post to remove forward tags and re-applies exact button styles."""
    markup = reply_markup if reply_markup is not None else msg.reply_markup
    for _ in range(5):
        try:
            sent = None
            if msg.media:
                caption = custom_caption if custom_caption is not None else (msg.caption or "")
                sent = await msg.copy(
                    chat_id, 
                    caption=caption, 
                    parse_mode=parse_mode if custom_caption else None,
                    reply_markup=markup, 
                    disable_notification=True
                )
            else:
                text = custom_caption if custom_caption is not None else (msg.text or "")
                sent = await app.send_message(
                    chat_id=chat_id, 
                    text=text, 
                    parse_mode=parse_mode if custom_caption else None,
                    reply_markup=markup, 
                    disable_notification=True, 
                    disable_web_page_preview=False
                )
            
            # Explicitly enforce reply markup with colors after copying
            if sent and markup:
                try:
                    await app.edit_message_reply_markup(chat_id=chat_id, message_id=sent.id, reply_markup=markup)
                except Exception:
                    pass
                    
            await asyncio.sleep(0.4)
            await msg.delete()
            return sent
        except Exception as e:
            if "FLOOD_WAIT" in str(e):
                wait_sec = int(re.search(r'(\d+)', str(e)).group(1)) + 2
                await asyncio.sleep(wait_sec)
                continue
            logger.error(f"[AUTO-BUTTON] safe_copy_and_delete error: {e}")
            return None
    return None

# -------------------- AUTOMATIC CAPTION LINK & BUTTON DISPATCHER -------------------- #
async def process_channel_post_auto_buttons(client, message: Message):
    """
    Detects trigger links or URLs in channel posts, strips them,
    replaces {link} in the active button template, and attaches colored buttons to the post.
    """
    chat_id = message.chat.id
    chat_username = message.chat.username

    # Step 1: Verify channel authorization; auto-authorize if bot is admin
    settings = await get_channel_settings(chat_id, chat_username)
    if not settings:
        try:
            member = await client.get_chat_member(chat_id, "me")
            priv = getattr(member, "privileges", None)
            if priv and (getattr(priv, "can_post_messages", False) or getattr(priv, "can_edit_messages", False)):
                await add_auth_channel(chat_id, forward_tag=False, auto_accept_time="1s")
                settings = await get_channel_settings(chat_id, chat_username)
        except Exception as e:
            logger.debug(f"[AUTO-BUTTON] Chat {chat_id} is not authorized: {e}")

    if not settings:
        return

    raw_text = message.caption or message.text or ""
    entities = message.caption_entities or message.entities or []

    # Step 2: Fetch the active button template
    template_data = await get_effective_template(chat_id, chat_username)
    if not template_data:
        # Fallback to any recent template in database
        template_data = await btn_templatedb.find_one({"template": {"$exists": True, "$ne": ""}}, sort=[("updated_at", -1), ("_id", -1)])
        if not template_data:
            return

    template = template_data.get("template", "")
    font_style = template_data.get("font_style", "sim")
    needs_link = bool(re.search(r"\{\s*(?:link|url|target)\s*\}", template, re.IGNORECASE))

    # Step 3: Extract the URL from post
    html_text = get_html_text(raw_text, entities)
    extracted_link, cleaned_raw, cleaned_html = extract_trigger_link_and_clean_caption(raw_text, html_text)

    # If the template requires a {link} placeholder, but no link was found in the post, skip
    if needs_link and not extracted_link:
        # If forwarded and tag removal is enabled, still clean forward tag
        if settings.get("forward_tag_removal") and is_forwarded(message):
            await asyncio.sleep(0.3)
            await safe_copy_and_delete(message, chat_id)
        return

    logger.info(f"[AUTO-BUTTON] Processing post {message.id} in {chat_id} (Link: {extracted_link})")

    # Step 4: Generate Keyboard with replacement link
    final_btn_text = template
    if extracted_link:
        final_btn_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", extracted_link, template, flags=re.IGNORECASE)

    keyboard = parse_buttons(final_btn_text, font_style=font_style)
    if not keyboard:
        logger.error("[AUTO-BUTTON] Could not parse buttons from template!")
        return

    # Step 5: Format the cleaned caption
    final_caption_html = apply_font_to_caption(cleaned_html, font_style) if font_style != "normal" else cleaned_html
    final_caption_raw = apply_font_to_caption(cleaned_raw, font_style) if font_style != "normal" else cleaned_raw

    # Step 6: If forward tag removal is enabled and message is forwarded, copy and delete
    if settings.get("forward_tag_removal") and is_forwarded(message):
        await asyncio.sleep(0.3)
        await safe_copy_and_delete(message, chat_id, custom_caption=final_caption_html, reply_markup=keyboard)
        return

    # Step 7: Edit the post in place with buttons and formatted text
    try:
        if message.media:
            await client.edit_message_caption(
                chat_id=chat_id,
                message_id=message.id,
                caption=final_caption_html,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await client.edit_message_text(
                chat_id=chat_id,
                message_id=message.id,
                text=final_caption_html,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        # Re-enforce reply markup to guarantee color rendering
        try:
            await client.edit_message_reply_markup(chat_id=chat_id, message_id=message.id, reply_markup=keyboard)
        except Exception:
            pass
        logger.info(f"[AUTO-BUTTON] Successfully auto-attached buttons to post {message.id}!")
    except Exception as html_err:
        logger.warning(f"[AUTO-BUTTON] HTML edit failed: {html_err}. Retrying with plain text...")
        try:
            if message.media:
                await client.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message.id,
                    caption=final_caption_raw,
                    parse_mode=None,
                    reply_markup=keyboard
                )
            else:
                await client.edit_message_text(
                    chat_id=chat_id,
                    message_id=message.id,
                    text=final_caption_raw,
                    parse_mode=None,
                    reply_markup=keyboard
                )
            try:
                await client.edit_message_reply_markup(chat_id=chat_id, message_id=message.id, reply_markup=keyboard)
            except Exception:
                pass
            logger.info(f"[AUTO-BUTTON] Successfully auto-attached buttons (Plain Text) to post {message.id}!")
        except Exception as plain_err:
            err_str = str(plain_err).upper()
            if "MESSAGE_NOT_MODIFIED" in err_str:
                try:
                    await client.edit_message_reply_markup(chat_id=chat_id, message_id=message.id, reply_markup=keyboard)
                except Exception:
                    pass
            elif any(k in err_str for k in ["MESSAGE_AUTHOR_REQUIRED", "CHAT_ADMIN_REQUIRED", "CHAT_WRITE_FORBIDDEN"]):
                logger.warning("[AUTO-BUTTON] Bot lacks edit rights of others. Reposting to apply buttons...")
                await safe_copy_and_delete(
                    message, 
                    chat_id, 
                    custom_caption=final_caption_html, 
                    reply_markup=keyboard
                )
            else:
                logger.error(f"[AUTO-BUTTON] Failed to update post {message.id}: {plain_err}")

@app.on_message((filters.channel | filters.group) & ~filters.service)
async def channel_post_listener(client, message: Message):
    await process_channel_post_auto_buttons(client, message)

@app.on_edited_message((filters.channel | filters.group) & ~filters.service)
async def channel_post_edit_listener(client, message: Message):
    await process_channel_post_auto_buttons(client, message)

# -------------------- AUTO JOIN REQUEST APPROVAL -------------------- #
@app.on_chat_join_request()
async def auto_approve_join_request(client, request: ChatJoinRequest):
    settings = await get_channel_settings(request.chat.id)
    if settings:
        await asyncio.sleep(settings["auto_accept_seconds"])
        try: 
            await client.approve_chat_join_request(chat_id=request.chat.id, user_id=request.from_user.id)
        except Exception: 
            pass
