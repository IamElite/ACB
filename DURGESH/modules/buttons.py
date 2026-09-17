import re
import asyncio
import time
import logging
from typing import Dict, Optional, Tuple, List, Union
import pyrogram
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from pyrogram.enums import ParseMode

logger = logging.getLogger("buttons")
logging.basicConfig(level=logging.INFO)

from DURGESH import app
from DURGESH.database import db

authdb = db.auth_channels
btn_templatedb = db.button_templates

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
    "r": RED_STYLE, "red": RED_STYLE, "danger": RED_STYLE, "d": RED_STYLE,
    "g": GREEN_STYLE, "green": GREEN_STYLE, "success": GREEN_STYLE, "s": GREEN_STYLE,
    "b": BLUE_STYLE, "blue": BLUE_STYLE, "primary": BLUE_STYLE, "p": BLUE_STYLE,
    "none": None, "normal": None, "default": None, "off": None
}

ASCII_LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
ASCII_ALPHANUM = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'

FONTS = {
    's': dict(zip(ASCII_LETTERS, 'ᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢ')),
    'sm': dict(zip(ASCII_ALPHANUM, 'ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿')),
    'sim': dict(zip(ASCII_LETTERS, '𝖠𝖡𝖢𝖣𝖤𝖥𝖦𝖧𝖨𝖩𝖪𝖫𝖬𝖭𝖮𝖯𝖰𝖱𝖲𝖳𝖴𝖵𝖶𝖷𝖸𝖹𝖺𝖻𝖼𝖽𝖾𝖿𝗀𝗁𝗂𝗃𝗄𝗅𝗆𝗇𝗈𝗉𝗊𝗋𝗌𝗍𝗎𝗏𝗐𝗑𝗒𝗓')),
    'san': dict(zip(ASCII_ALPHANUM, '𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵'))
}
FONTS['a'] = FONTS['sim']
FONTS['b'] = FONTS['san']

REVERSE_MAP = {char: orig for font_dict in FONTS.values() for orig, char in font_dict.items()}

def apply_font(text: str, font_style: str) -> str:
    """Normalizes custom text styles back to standard ASCII, then applies target font."""
    font = FONTS.get(font_style)
    if not font:
        return text
    clean = "".join(REVERSE_MAP.get(c, c) for c in text)
    return "".join(font.get(c, c) for c in clean)

def sanitize_button_url(url: str) -> Optional[str]:
    """Cleans URLs, resolves telegram shortlinks/handles, and verifies schemes."""
    if not url:
        return None
    clean = re.sub(r'[\u200b-\u200f\ufeff\u00a0\r\n]+', '', url.strip().strip("'\"<>`"))
    if not clean or re.match(r'^\{.*\}$', clean):
        return None
    if clean.startswith("@"):
        return f"https://t.me/{clean.lstrip('@')}"
    if match := re.match(r'^([a-zA-Z0-9_]{4,})\.t\.me(?:/(.*))?$', clean, re.IGNORECASE):
        return f"https://t.me/{match.group(1)}{'/' + match.group(2) if match.group(2) else ''}"
    if re.match(r'^(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/', clean, re.IGNORECASE):
        return f"https://{clean}"
    if not clean.startswith(("http://", "https://", "tg://")):
        return f"https://{clean}" if re.match(r'^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}', clean) else None
    return clean

def parse_time_to_seconds(time_str: str) -> int:
    match = re.match(r'^(\d+)([smhd])$', (time_str or "").strip().lower())
    return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(match.group(2), 1) if match else 1

def _chat_id_queries(chat_id: Union[int, str], username: Optional[str] = None) -> List[Dict]:
    cid = str(chat_id)
    raw = cid.replace("-100", "").replace("-", "")
    queries = [{"chat_id": cid}]
    if raw.isdigit():
        queries.extend([{"chat_id": int(cid)}, {"chat_id": raw}, {"chat_id": int(raw)},
                        {"chat_id": f"-100{raw}"}, {"chat_id": int(f"-100{raw}")}])
    if username:
        clean = username.lstrip("@").lower()
        queries.extend([{"chat_id": f"@{clean}"}, {"chat_id": clean}])
    return queries

async def add_auth_channel(chat_id: int, forward_tag: bool = True, auto_accept_time: str = "1s", admin_id: Optional[int] = None):
    doc = {
        "chat_id": str(chat_id),
        "forward_tag_removal": forward_tag,
        "auto_accept_time": auto_accept_time,
        "auto_accept_seconds": parse_time_to_seconds(auto_accept_time)
    }
    if admin_id:
        doc["admin_id"] = str(admin_id)
    await authdb.update_one({"$or": _chat_id_queries(chat_id)}, {"$set": doc}, upsert=True)

async def remove_auth_channel(chat_id: int):
    await authdb.delete_many({"$or": _chat_id_queries(chat_id)})

async def get_channel_settings(chat_id: int, username: Optional[str] = None) -> Optional[Dict]:
    return await authdb.find_one({"$or": _chat_id_queries(chat_id, username)})

async def is_channel_authed(chat_id: int, username: Optional[str] = None) -> bool:
    return bool(await get_channel_settings(chat_id, username))

async def save_button_template(user_id: int, template: str, font_style: str = "sim"):
    data = {"template": template, "font_style": font_style, "updated_at": time.time(), "user_id": str(user_id)}
    await btn_templatedb.update_one({"$or": [{"user_id": str(user_id)}, {"user_id": user_id}]}, {"$set": data}, upsert=True)
    await btn_templatedb.update_one({"_id": "GLOBAL_ACTIVE_TEMPLATE"}, {"$set": data}, upsert=True)
    await authdb.update_many({}, {"$set": {"admin_id": str(user_id)}})

async def get_button_template(user_id: Union[int, str]) -> Optional[Dict]:
    uid = str(user_id)
    return (await btn_templatedb.find_one({"$or": [{"user_id": uid}, {"user_id": int(uid) if uid.isdigit() else uid}]})) or \
           (await btn_templatedb.find_one({"_id": "GLOBAL_ACTIVE_TEMPLATE"}))

async def get_effective_template(chat_id: Optional[int] = None, username: Optional[str] = None) -> Optional[Dict]:
    if chat_id:
        settings = await get_channel_settings(chat_id, username)
        if settings and settings.get("admin_id"):
            if tmpl := await get_button_template(settings["admin_id"]):
                return tmpl
    return (await btn_templatedb.find_one({"_id": "GLOBAL_ACTIVE_TEMPLATE"})) or \
           (await btn_templatedb.find_one({"template": {"$exists": True, "$ne": ""}}, sort=[("updated_at", -1)]))

async def delete_button_template(user_id: int):
    uid = str(user_id)
    await btn_templatedb.delete_many({"$or": [{"user_id": uid}, {"user_id": user_id}, {"_id": "GLOBAL_ACTIVE_TEMPLATE", "user_id": uid}]})

def create_button(text: str, url: str, style=RED_STYLE) -> InlineKeyboardButton:
    """Creates a button defaulting to Red (Danger) across Pyrogram and its active forks."""
    chosen_style = RED_STYLE if style is None else style
    if chosen_style in ["none", "normal", "default", "off"]:
        return InlineKeyboardButton(text, url=url)

    for attr in ("style", "color"):
        for val in (chosen_style, getattr(chosen_style, "value", str(chosen_style)).lower()):
            try:
                return InlineKeyboardButton(text, url=url, **{attr: val})
            except (TypeError, ValueError):
                continue
    return InlineKeyboardButton(text, url=url)

URL_REGEX = re.compile(
    r'(\{\s*(?:link|url|target)\s*\}|https?://[^\s<>"\']+|tg://[^\s<>"\']+|t\.me/[^\s<>"\']+|@[a-zA-Z0-9_]{4,}|(?:[a-zA-Z0-9_\-]+\.)+[a-zA-Z]{2,}/[^\s<>"\']*)',
    re.IGNORECASE
)

def parse_buttons(text: str, font_style: str = "sim", default_color=RED_STYLE) -> Optional[InlineKeyboardMarkup]:
    """Parses button templates, preserving titles containing '+' and applying default red styling."""
    if not text:
        return None
    lines = re.sub(r'\]\[', ']\n[', text.strip()).splitlines()
    keyboard = []

    for line in lines:
        if not line.strip():
            continue
        row = []
        for content, out_color in re.findall(r'\[([^\]]+)\](?:\s*[:\-–—|]?\s*(?:\[(\w+)\]|\((\w+)\)|(\w+)))?', line):
            color_suffix = next((c.lower() for c in out_color if c), "")
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

ENTITY_TAGS = {
    "bold": ("<b>", "</b>"), "italic": ("<i>", "</i>"), "code": ("<code>", "</code>"),
    "strikethrough": ("<s>", "</s>"), "strike": ("<s>", "</s>"), "underline": ("<u>", "</u>"),
    "spoiler": ("<spoiler>", "</spoiler>"), "blockquote": ("<blockquote>", "</blockquote>"),
    "expandable_blockquote": ("<blockquote expandable>", "</blockquote>"),
    "expandableblockquote": ("<blockquote expandable>", "</blockquote>")
}

def _entity_name(entity) -> str:
    etype = getattr(entity, "type", None)
    if isinstance(etype, str): return etype.lower()
    if name := getattr(etype, "name", None): return str(name).lower()
    val = getattr(etype, "value", None)
    if isinstance(val, type): return val.__name__.lower()
    if isinstance(val, str): return val.lower()
    return getattr(etype, "__name__", str(etype)).lower()

def get_html_text(text: str, entities: list) -> str:
    """Formats raw caption with HTML tags, preventing crashes on TL schema type entities."""
    if not text or not entities:
        return text or ""
    try:
        raw_bytes = text.encode("utf-16-le")
    except Exception:
        return text

    events = {}
    for i, e in enumerate(entities):
        ename = _entity_name(e)
        start, end = e.offset * 2, (e.offset + e.length) * 2
        s_tag, e_tag = ENTITY_TAGS.get(ename, ("", ""))
        if "pre" in ename:
            s_tag, e_tag = f'<pre><code class="language-{getattr(e, "language", "") or ""}">', "</code></pre>"
        elif "text_link" in ename or "texturl" in ename:
            s_tag, e_tag = f'<a href="{getattr(e, "url", "")}">', "</a>"
        elif ("text_mention" in ename or "mentionname" in ename) and getattr(e, "user", None):
            s_tag, e_tag = f'<a href="tg://user?id={e.user.id}">', "</a>"

        if s_tag:
            events.setdefault(start, []).append(("start", i, s_tag))
            events.setdefault(end, []).append(("end", i, e_tag))

    output = []
    last = 0
    for idx in sorted(events):
        output.append(raw_bytes[last:idx].decode("utf-16-le"))
        ends = sorted([ev for ev in events[idx] if ev[0] == "end"], key=lambda x: x[1], reverse=True)
        starts = sorted([ev for ev in events[idx] if ev[0] == "start"], key=lambda x: x[1])
        output.extend(ev[2] for ev in ends + starts)
        last = idx
    output.append(raw_bytes[last:].decode("utf-16-le"))
    return "".join(output)

LINK_PATTERNS = [
    re.compile(r'(?:^|\n|\s)[-–—~•👉🔗>]\s*<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\'][^>]*>.*?</a>', re.IGNORECASE),
    re.compile(r'(?:^|\n|\s)[-–—~•👉🔗>]\s*(https?://[^\s<>"\']+|t\.me/[^\s<>"\']+)', re.IGNORECASE),
    re.compile(r'(?:^|\n)\s*(https?://[^\s<>"\']+|t\.me/[^\s<>"\']+)\s*(?:\n|$)', re.IGNORECASE),
    re.compile(r'(https?://[^\s<>"\']+|t\.me/[^\s<>"\']+)', re.IGNORECASE)
]

def extract_trigger_link_and_clean_caption(raw_text: str, html_text: str) -> Tuple[Optional[str], str, str]:
    target = html_text or raw_text or ""
    for pattern in LINK_PATTERNS:
        if match := pattern.search(target):
            url = sanitize_button_url(match.group(1).strip())
            cl_html = re.sub(r'\n{3,}', '\n\n', pattern.sub('', target)).strip()
            cl_raw = re.sub(r'\n{3,}', '\n\n', pattern.sub('', raw_text)).strip() if raw_text else cl_html
            return url, cl_raw, cl_html
    return None, raw_text or "", html_text or ""

def apply_font_to_caption(caption: str, font_style: str) -> str:
    if not caption or font_style == "normal":
        return caption
    lines = []
    regex = re.compile(r'(<[^>]+>|https?://[^\s]+|t\.me/[^\s]+|tg://[^\s]+)')
    for line in caption.splitlines():
        if any(ign in line.lower() for ign in ("syntaxrealm.t.me", "❖", "made by")):
            lines.append(line)
        else:
            lines.append("".join(part if regex.match(part) else apply_font(part, font_style) for part in regex.split(line)))
    return "\n".join(lines)

def extract_chat_and_msg_id(link: str) -> Tuple[Optional[int], Optional[int]]:
    if priv := re.match(r"https?://t\.me/c/(-?\d+)/(\d+)", link.strip()):
        raw = priv.group(1).lstrip("-")
        return (int(f"-{raw}") if raw.startswith("100") else int(f"-100{raw}")), int(priv.group(2))
    return None, None

def get_forward_chat(msg: Optional[Message]):
    if not msg: return None
    if origin := getattr(msg, "forward_origin", None):
        return getattr(origin, "chat", None) or getattr(origin, "sender_chat", None)
    return getattr(msg, "forward_from_chat", None)

async def safe_copy_and_delete(msg: Message, chat_id: int, caption: Optional[str] = None, reply_markup: Optional[InlineKeyboardMarkup] = None) -> Optional[Message]:
    markup = reply_markup if reply_markup is not None else msg.reply_markup
    for _ in range(3):
        try:
            if msg.media:
                sent = await msg.copy(chat_id, caption=caption or (msg.caption or ""), parse_mode=ParseMode.HTML if caption else None, reply_markup=markup)
            else:
                sent = await app.send_message(chat_id, text=caption or (msg.text or ""), parse_mode=ParseMode.HTML if caption else None, reply_markup=markup, disable_web_page_preview=False)
            await asyncio.sleep(0.3)
            await msg.delete()
            return sent
        except Exception as e:
            if "FLOOD_WAIT" in str(e):
                await asyncio.sleep(int(re.search(r'\d+', str(e)).group()) + 2)
    return None

@app.on_message(filters.command(["auth"]))
async def auth_channel_cmd(client, message: Message):
    args = message.text.split()
    fwd = get_forward_chat(message.reply_to_message)
    chat_id = fwd.id if fwd else None
    f_tag = not ("-f" in args and args[args.index("-f") + 1].lower() in ["off", "false", "0"])
    ac_time = args[args.index("-ac") + 1] if "-ac" in args and args.index("-ac") + 1 < len(args) else "1s"

    if not chat_id and len(args) > 1 and not args[1].startswith("-"):
        try:
            chat_id = (await client.get_chat(args[1])).id
        except Exception as e:
            return await message.reply_text(f"❌ Invalid channel: {e}")

    if not chat_id:
        return await message.reply_text("❌ Usage: `/auth <channel_id>` or reply to a forwarded message.")

    await add_auth_channel(chat_id, f_tag, ac_time, message.from_user.id if message.from_user else None)
    await message.reply_text(f"✅ **Channel Authorized:** `{chat_id}`\n🔄 Forward Tag Removal: `{'ON' if f_tag else 'OFF'}`\n⏱ Auto-Accept: `{ac_time}`")

@app.on_message(filters.command(["unauth"]))
async def unauth_channel_cmd(client, message: Message):
    args = message.command
    fwd = get_forward_chat(message.reply_to_message)
    chat_id = fwd.id if fwd else (int(args[1]) if len(args) > 1 and args[1].lstrip("-").isdigit() else None)
    if not chat_id:
        return await message.reply_text("❌ Usage: `/unauth <channel_id>` or reply to a forwarded post.")
    await remove_auth_channel(chat_id)
    await message.reply_text(f"✅ Un-Authorized: `{chat_id}`")

@app.on_message(filters.command(["ab", "abset", "absee", "abseen", "abrm"]))
async def auto_button_commands(client, message: Message):
    cmd = message.command[0].lower()
    user_id = message.from_user.id

    if cmd == "abrm":
        await delete_button_template(user_id)
        return await message.reply_text("🗑️ Button template remove kar diya gaya hai!")

    if cmd in ["absee", "abseen"]:
        data = await get_button_template(user_id)
        if not data:
            return await message.reply_text("❌ Koi template set nahi hai! Pehle `/abset` karein.")
        preview = re.sub(r"\{\s*(?:link|url|target)\s*\}", "https://t.me/PreviewDemo", data["template"], flags=re.IGNORECASE)
        kb = parse_buttons(preview, font_style=data.get("font_style", "sim"))
        return await message.reply_text(f"📋 **Active Template:**\n`{data['template']}`\n🔴 **Default Color:** `Red`\n🎨 **Font:** `{data.get('font_style', 'sim')}`", reply_markup=kb)

    if cmd == "abset":
        raw = message.reply_to_message.text or message.reply_to_message.caption if message.reply_to_message else message.text
        font = (re.search(r"-f\s+(\w+)", raw).group(1).lower() if re.search(r"-f\s+(\w+)", raw) else "sim")
        tmpl = re.sub(r"^/abset\s*", "", re.sub(r"-f\s+\w+", "", raw)).strip()
        if not tmpl:
            return await message.reply_text("❌ Template provide karein! Format: `[Text + {link}]`")
        kb = parse_buttons(re.sub(r"\{\s*(?:link|url|target)\s*\}", "https://t.me/PreviewDemo", tmpl, flags=re.IGNORECASE), font_style=font)
        if not kb:
            return await message.reply_text("❌ Invalid buttons! Format: `[Name + {link}]`")
        await save_button_template(user_id, tmpl, font)
        return await message.reply_text(f"✅ **Button Template Set!**\n🔴 **Default Color:** `Red (Danger)`\n🎨 **Font:** `{font}`", reply_markup=kb)

    # Manual /ab <post_link>
    if cmd == "ab":
        if not message.command[1:]:
            return await message.reply_text("❌ Usage: `/ab <target_post_link>`")
        target_link = message.command[1]
        cid, mid = extract_chat_and_msg_id(target_link)
        if not cid:
            if match := re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", target_link):
                try: cid, mid = (await client.get_chat(match.group(1))).id, int(match.group(2))
                except Exception as e: return await message.reply_text(f"❌ Error: {e}")
        if not cid:
            return await message.reply_text("❌ Invalid link format!")

        tmpl_data = await get_effective_template(cid)
        if not tmpl_data:
            return await message.reply_text("❌ Pehle `/abset` se template configure karein!")

        target_msg = await client.get_messages(cid, mid)
        raw_text = target_msg.caption or target_msg.text or ""
        html_text = get_html_text(raw_text, target_msg.caption_entities or target_msg.entities or [])

        rep_link = None
        if message.reply_to_message:
            rep_match = re.search(r"(https?://\S+)", message.reply_to_message.text or message.reply_to_message.caption or "")
            if rep_match: rep_link = rep_match.group(1)
        if not rep_link:
            rep_link, raw_text, html_text = extract_trigger_link_and_clean_caption(raw_text, html_text)

        if not rep_link:
            return await message.reply_text("❌ Replacement link nahi mila!")

        font_style = tmpl_data.get("font_style", "sim")
        final_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", rep_link, tmpl_data["template"], flags=re.IGNORECASE)
        kb = parse_buttons(final_text, font_style=font_style)

        caption = apply_font_to_caption(html_text, font_style)
        try:
            if target_msg.media:
                await client.edit_message_caption(cid, mid, caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await client.edit_message_text(cid, mid, text=caption, parse_mode=ParseMode.HTML, reply_markup=kb)
            await message.reply_text("✅ **Buttons Applied Successfully!**")
        except Exception as e:
            try:
                await client.edit_message_reply_markup(cid, mid, reply_markup=kb)
                await message.reply_text("✅ **Buttons Updated!**")
            except Exception as err:
                await message.reply_text(f"⚠️ Edit failed: {err}")

@app.on_message(filters.command(["cb"]))
async def change_button_cmd(client, message: Message):
    if not message.reply_to_message or len(message.command) < 2:
        return await message.reply_text("❌ Reply to button text with `/cb <post_link>`")
    cid, mid = extract_chat_and_msg_id(message.command[1])
    if not cid:
        return await message.reply_text("❌ Invalid post link!")
    kb = parse_buttons(message.reply_to_message.text or "", font_style="normal")
    if not kb:
        return await message.reply_text("❌ Invalid button syntax!")
    try:
        await client.edit_message_reply_markup(cid, mid, reply_markup=kb)
        await message.reply_text("✅ Buttons replaced!")
    except Exception as e:
        await message.reply_text(f"⚠️ Error: {e}")

@app.on_chat_join_request()
async def auto_accept_join(client, request: ChatJoinRequest):
    settings = await get_channel_settings(request.chat.id)
    if settings:
        await asyncio.sleep(settings.get("auto_accept_seconds", 1))
        try:
            await client.approve_chat_join_request(chat_id=request.chat.id, user_id=request.from_user.id)
        except Exception:
            pass

async def dispatch_channel_post(client, message: Message):
    """Processes newly posted or edited channel posts and attaches red buttons automatically."""
    chat_id = message.chat.id
    settings = await get_channel_settings(chat_id, message.chat.username)

    if not settings:
        settings = {"chat_id": str(chat_id), "forward_tag_removal": False, "auto_accept_seconds": 1}
        await add_auth_channel(chat_id, forward_tag=False, auto_accept_time="1s")

    tmpl_data = await get_effective_template(chat_id, message.chat.username)
    if not tmpl_data:
        return

    raw_text = message.caption or message.text or ""
    entities = message.caption_entities or message.entities or []
    html_text = get_html_text(raw_text, entities)

    extracted_url, cl_raw, cl_html = extract_trigger_link_and_clean_caption(raw_text, html_text)
    needs_link = bool(re.search(r"\{\s*(?:link|url|target)\s*\}", tmpl_data.get("template", ""), re.IGNORECASE))

    if needs_link and not extracted_url:
        if settings.get("forward_tag_removal") and getattr(message, "forward_date", None):
            await safe_copy_and_delete(message, chat_id)
        return

    font_style = tmpl_data.get("font_style", "sim")
    btn_text = tmpl_data.get("template", "")
    if extracted_url:
        btn_text = re.sub(r"\{\s*(?:link|url|target)\s*\}", extracted_url, btn_text, flags=re.IGNORECASE)

    keyboard = parse_buttons(btn_text, font_style=font_style, default_color=RED_STYLE)
    if not keyboard:
        return

    final_caption = apply_font_to_caption(cl_html, font_style) if font_style != "normal" else cl_html

    # If forwarded post tag removal is enabled
    if settings.get("forward_tag_removal") and getattr(message, "forward_date", None):
        await safe_copy_and_delete(message, chat_id, caption=final_caption, reply_markup=keyboard)
        return

    # Attempt in-place editing; fallback to clone-and-replace if bot lacks editing rights of another admin
    try:
        if message.media:
            await client.edit_message_caption(chat_id, message.id, caption=final_caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        else:
            await client.edit_message_text(chat_id, message.id, text=final_caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except Exception as e:
        logger.warning(f"[AUTO-BUTTON] In-place edit failed ({e}). Reposting with buttons...")
        await safe_copy_and_delete(message, chat_id, caption=final_caption, reply_markup=keyboard)

@app.on_message((filters.channel | filters.group) & ~filters.service)
async def channel_post_listener(client, message: Message):
    await dispatch_channel_post(client, message)

@app.on_edited_message((filters.channel | filters.group) & ~filters.service)
async def channel_post_edit_listener(client, message: Message):
    await dispatch_channel_post(client, message)
