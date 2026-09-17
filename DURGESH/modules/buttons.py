import re
import asyncio
from typing import Dict, Optional, Tuple
import pyrogram
from pyrogram import filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
)
from pyrogram.enums import ParseMode

# -------------------- BUTTON STYLE ENUM IMPORT -------------------- #
try:
    from pyrogram.enums import ButtonStyle
    RED_STYLE = ButtonStyle.DANGER
    GREEN_STYLE = ButtonStyle.SUCCESS
    BLUE_STYLE = ButtonStyle.PRIMARY
except ImportError:
    RED_STYLE = "danger"
    GREEN_STYLE = "success"
    BLUE_STYLE = "primary"

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

STYLE_SIM = {
    "a": "𝖺", "b": "𝖻", "c": "𝖼", "d": "𝖽", "e": "𝖾", "f": "𝖿", "g": "𝗀", "h": "𝗁",
    "i": "𝗂", "j": "𝗃", "k": "𝗄", "l": "𝗅", "m": "𝗆", "n": "𝗇", "o": "𝗈", "p": "𝗉",
    "q": "𝗊", "r": "𝗋", "s": "𝗌", "t": "𝗍", "u": "𝗎", "v": "𝗏", "w": "𝗐", "x": "𝗑",
    "y": "𝗒", "z": "𝗓", "A": "𝖠", "B": "𝖡", "C": "𝖢", "D": "𝖣", "E": "𝖤", "F": "𝖥",
    "G": "𝖦", "H": "𝖧", "I": "𝖨", "J": "𝖩", "K": "𝖪", "L": "𝖫", "M": "𝖬", "N": "𝖭",
    "O": "𝖮", "P": "𝖯", "Q": "𝖰", "R": "𝖱", "S": "𝖲", "T": "𝳮", "U": "𝖴", "V": "𝖵",
    "W": "𝖶", "X": "𝖷", "Y": "𝖸", "Z": "𝖹"
}

STYLE_SAN = {
    "a": "𝗮", "b": "𝗯", "c": "𝗰", "d": "𝗱", "e": "𝗲", "f": "𝗳", "g": "𝗴", "h": "𝗵",
    "i": "𝗶", "j": "𝗷", "k": "𝗸", "l": "𝗹", "m": "𝗺", "n": "𝗻", "o": "𝗼", "p": "𝗽",
    "q": "𝗾", "r": "𝗿", "s": "𝘀", "t": "𝘁", "u": "𝘂", "v": "𝘃", "w": "𝘄", "x": "𝘅",
    "y": "𝘆", "z": "𝘇", "A": "𝗔", "B": "𝗕", "C": "𝗖", "D": "𝗗", "E": "𝗘", "F": "𝗙",
    "G": "𝗚", "H": "𝗛", "I": "𝗜", "J": "𝗝", "K": "𝗞", "L": "𝗟", "M": "𝗠", "N": "𝗡",
    "O": "𝗢", "P": "𝗣", "Q": "𝗤", "R": "𝗥", "S": "𝗦", "T": "𝗧", "U": "𝗨", "V": "𝗩",
    "W": "𝗪", "X": "𝗫", "Y": "𝗬", "Z": "𝗭", "0": "𝟬", "1": "𝟭", "2": "𝟮", "3": "𝟯",
    "4": "𝟰", "5": "𝟱", "6": "𝟲", "7": "𝟳", "8": "𝟴", "9": "𝟵"
}

# REVERSE MAP: Converts any custom styled text back to normal A-Z
REVERSE_MAP = {}
for k, v in zip(FONT_S_KEYS, FONT_S_VALS):
    if v not in REVERSE_MAP: REVERSE_MAP[v] = k
for k, v in zip(FONT_SM_KEYS, FONT_SM_VALS):
    if v not in REVERSE_MAP: REVERSE_MAP[v] = k
for k, v in STYLE_SIM.items():
    if v not in REVERSE_MAP: REVERSE_MAP[v] = k
for k, v in STYLE_SAN.items():
    if v not in REVERSE_MAP: REVERSE_MAP[v] = k

def apply_font(text: str, font_style: str) -> str:
    """Un-styles text using REVERSE_MAP, then applies the requested font style."""
    normalized_text = ''.join(REVERSE_MAP.get(c, c) for c in text)
    if font_style == 's': return ''.join(FONT_S.get(c, c) for c in normalized_text)
    elif font_style == 'sm': return ''.join(FONT_SM.get(c, c) for c in normalized_text)
    elif font_style in ['sim', 'a']: return ''.join(STYLE_SIM.get(c, c) for c in normalized_text)
    elif font_style in ['san', 'b']: return ''.join(STYLE_SAN.get(c, c) for c in normalized_text)
    return normalized_text

# -------------------- DB HELPERS & TIME PARSER -------------------- #
def parse_time_to_seconds(time_str: str) -> int:
    if not time_str: return 1
    match = re.match(r'^(\d+)([smhd])$', time_str.strip().lower())
    if not match: return 1
    return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(match.group(2), 1)

async def add_auth_channel(chat_id: int, forward_tag: bool = True, auto_accept_time: str = "1s", admin_id: Optional[int] = None):
    payload = {
        "chat_id": str(chat_id),
        "forward_tag_removal": forward_tag,
        "auto_accept_time": auto_accept_time,
        "auto_accept_seconds": parse_time_to_seconds(auto_accept_time)
    }
    if admin_id:
        payload["admin_id"] = str(admin_id)
    await authdb.update_one({"chat_id": str(chat_id)}, {"$set": payload}, upsert=True)

async def remove_auth_channel(chat_id: int): 
    await authdb.delete_one({"chat_id": str(chat_id)})

async def is_channel_authed(chat_id: int) -> bool: 
    return bool(await authdb.find_one({"chat_id": str(chat_id)}))

async def get_channel_settings(chat_id: int) -> Optional[Dict]:
    data = await authdb.find_one({"chat_id": str(chat_id)})
    if data:
        return {
            "forward_tag_removal": data.get("forward_tag_removal", True),
            "auto_accept_time": data.get("auto_accept_time", "1s"),
            "auto_accept_seconds": data.get("auto_accept_seconds", 1),
            "admin_id": data.get("admin_id")
        }
    return None

async def save_button_template(user_id: int, template: str, font_style: str = "sim"):
    await btn_templatedb.update_one(
        {"user_id": str(user_id)}, 
        {"$set": {"template": template, "font_style": font_style}}, 
        upsert=True
    )

async def get_button_template(user_id: int) -> Optional[Dict]:
    return await btn_templatedb.find_one({"user_id": str(user_id)})

async def get_effective_template(chat_id: int) -> Optional[Dict]:
    """Finds the button template configured for the channel's admin or falls back to the latest active template."""
    settings = await get_channel_settings(chat_id)
    if settings and settings.get("admin_id"):
        tmpl = await get_button_template(settings["admin_id"])
        if tmpl:
            return tmpl
    # Fallback: get the most recently saved template from any admin
    return await btn_templatedb.find_one(sort=[("_id", -1)])

async def delete_button_template(user_id: int):
    await btn_templatedb.delete_one({"user_id": str(user_id)})

# -------------------- LINK & ID EXTRACTORS -------------------- #
def extract_chat_and_msg_id(link: str) -> Tuple[Optional[int], Optional[int]]:
    """Accurately extracts channel/chat ID and message ID from both public and private Telegram links."""
    link = link.strip()
    pub = re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", link)
    if pub:
        return None, None # Will be resolved via get_chat username
    priv = re.match(r"https?://t\.me/c/(-?\d+)/(\d+)", link)
    if priv:
        raw_id = priv.group(1).lstrip("-")
        chat_id = int(f"-{raw_id}") if raw_id.startswith("100") else int(f"-100{raw_id}")
        return chat_id, int(priv.group(2))
    return None, None

def create_button(text: str, url: str, style=RED_STYLE):
    try: 
        return InlineKeyboardButton(text, url=url, style=style)
    except TypeError: 
        return InlineKeyboardButton(text, url=url)

def parse_buttons(text: str, font_style: str = "sim") -> Optional[InlineKeyboardMarkup]:
    keyboard = []
    for line in text.strip().splitlines():
        btns = []
        for match in re.finditer(r"\[([^\]]+?)\s*\+\s*(https?://[^\s\]]+)\]\s*([rgbRGB]?)", line):
            label = match.group(1).strip()
            link = match.group(2).strip()
            color_code = match.group(3).strip().lower()
            
            styled_label = apply_font(label, font_style) if font_style != "normal" else label
            color_map = {"r": RED_STYLE, "g": GREEN_STYLE, "b": BLUE_STYLE}
            btn_style = color_map.get(color_code, RED_STYLE)
            btns.append(create_button(styled_label, link, style=btn_style))
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
        
        if e.type == pyrogram.enums.MessageEntityType.BOLD:
            start_tag, end_tag = "<b>", "</b>"
        elif e.type == pyrogram.enums.MessageEntityType.ITALIC:
            start_tag, end_tag = "<i>", "</i>"
        elif e.type == pyrogram.enums.MessageEntityType.CODE:
            start_tag, end_tag = "<code>", "</code>"
        elif e.type == pyrogram.enums.MessageEntityType.PRE:
            lang = getattr(e, "language", "") or ""
            start_tag, end_tag = f'<pre><code class="language-{lang}">', "</code></pre>"
        elif e.type == pyrogram.enums.MessageEntityType.TEXT_LINK:
            start_tag, end_tag = f'<a href="{e.url}">', "</a>"
        elif e.type == pyrogram.enums.MessageEntityType.TEXT_MENTION:
            start_tag, end_tag = f'<a href="tg://user?id={e.user.id}">', "</a>"
        elif e.type == pyrogram.enums.MessageEntityType.STRIKETHROUGH:
            start_tag, end_tag = "<s>", "</s>"
        elif e.type == pyrogram.enums.MessageEntityType.UNDERLINE:
            start_tag, end_tag = "<u>", "</u>"
        elif e.type == pyrogram.enums.MessageEntityType.SPOILER:
            start_tag, end_tag = "<spoiler>", "</spoiler>"
        elif e.type == pyrogram.enums.MessageEntityType.BLOCKQUOTE:
            start_tag, end_tag = "<blockquote>", "</blockquote>"
        elif getattr(pyrogram.enums.MessageEntityType, "EXPANDABLE_BLOCKQUOTE", None) and e.type == pyrogram.enums.MessageEntityType.EXPANDABLE_BLOCKQUOTE:
            start_tag, end_tag = "<blockquote expandable>", "</blockquote>"

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
def extract_and_clean_caption_link(html_text: str) -> Tuple[Optional[str], str]:
    """
    Detects '-https://...' or '-http://...' (or its hyperlinked HTML tag equivalent) in the caption.
    Extracts the clean destination URL and removes the trigger '-https...' part from the text.
    """
    if not html_text:
        return None, html_text

    # Pattern matches:
    # 1. -<a href="URL">...</a>
    # 2. -https://... or -http://...
    pattern = re.compile(
        r'(?:^|(?<=\s))-(?:<a\s+(?:[^>]*?\s+)?href=["\']([^"\']+)["\'][^>]*>.*?</a>|(https?://[^\s<>"\']+))',
        re.IGNORECASE
    )
    match = pattern.search(html_text)
    if not match:
        return None, html_text

    extracted_url = match.group(1) or match.group(2)
    # Remove the matched pattern from the text
    cleaned_html = pattern.sub('', html_text)
    # Remove any unwanted leftover empty lines
    cleaned_html = re.sub(r'\n{3,}', '\n\n', cleaned_html).strip()
    return extracted_url, cleaned_html

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
    
    if message.reply_to_message and message.reply_to_message.forward_from_chat: 
        chat_id = message.reply_to_message.forward_from_chat.id
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
        return await message.reply_text(f"⚠️ Error: {e}")
    
    admin_id = message.from_user.id if message.from_user else None
    await add_auth_channel(chat_id, forward_tag, auto_accept_time, admin_id=admin_id)
    await message.reply_text(
        f"✅ **Channel Authorized!**\n"
        f"🆔 ID: `{chat_id}`\n"
        f"🔄 Forward Tag: `{'ON' if forward_tag else 'OFF'}`\n"
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
    elif message.reply_to_message and message.reply_to_message.forward_from_chat: 
        chat_id = message.reply_to_message.forward_from_chat.id
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
        preview_text = template_text.replace("{link}", "https://t.me/PreviewDemo")
        preview_keyboard = parse_buttons(preview_text, font_style=font_style)
        font_display = {"sim": "Sim (Serif)", "san": "San (Bold)", "s": "Small Caps", "sm": "Small+Num", "normal": "Default"}
        return await message.reply_text(
            f"📋 **Aapka Button Template:**\n`{template_text}`\n\n"
            f"🎨 **Font:** `{font_display.get(font_style, font_style)}`\n"
            f"👇 **Button Preview:**",
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
            
        keyboard = parse_buttons(template_text, font_style=font_style)
        if not keyboard: 
            return await message.reply_text("❌ Koi valid button nahi mila! Format: `[Text + URL] r`")
            
        await save_button_template(message.from_user.id, template_text, font_style)
        
        preview_text = template_text.replace("{link}", "https://t.me/PreviewDemo")
        preview_keyboard = parse_buttons(preview_text, font_style=font_style)
        font_display = {"sim": "Sim (Serif)", "san": "San (Bold)", "s": "Small Caps", "sm": "Small+Num", "normal": "Default"}
        
        return await message.reply_text(
            f"✅ **Button Template Set Ho Gaya!**\n"
            f"🎨 **Font:** `{font_display.get(font_style, font_style)}`\n"
            f"👇 **Niche Live Preview:**",
            reply_markup=preview_keyboard
        )

    if cmd == "ab":
        if not args:
            return await message.reply_text(
                "❌ **Usage Guide:**\n"
                "1️⃣ **Set Template:** `/abset` (reply to template text)\n"
                "2️⃣ **Apply Template:** `/ab <target_post_link>` (reply to message containing replacement link)"
            )
            
        target_link = args[0]
        replacement_link = None
        
        if message.reply_to_message:
            replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
            url_match = re.search(r"(https?://\S+)", replied_text)
            if url_match: 
                replacement_link = url_match.group(1)
            
        if not replacement_link:
            return await message.reply_text("❌ Replacement link wale message ko reply karke `/ab <target_post_link>` karein!")
            
        template_data = await get_button_template(message.from_user.id)
        if not template_data: 
            return await message.reply_text("❌ Pehle `/abset` se template set karein!")
            
        template, font_style = template_data["template"], template_data.get("font_style", "sim")
            
        # Extract target channel & message id safely
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
                
        final_text = re.sub(r"\{link\}", replacement_link, template, flags=re.IGNORECASE)
        keyboard = parse_buttons(final_text, font_style=font_style)
        if not keyboard: 
            return await message.reply_text("❌ Buttons parse nahi ho paye.")
            
        try:
            target_msg = await client.get_messages(channel_id, msg_id)
            original_text = target_msg.caption or target_msg.text
            original_entities = target_msg.caption_entities or target_msg.entities
            
            if original_text:
                html_text = get_html_text(original_text, original_entities)
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
                    await message.reply_text(f"✅ **Buttons & Font Successfully Applied!**")
                except Exception as edit_err:
                    # FIX: Handles same post re-edit gracefully if caption text is unchanged
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
        await message.reply_text("✅ Buttons updated with custom colors!")
    except Exception as e:
        if "MESSAGE_NOT_MODIFIED" in str(e).upper():
            await message.reply_text("ℹ️ **Same buttons already present!**")
        else:
            await message.reply_text(f"⚠️ Edit fail: {e}")

# -------------------- FORWARD TAG REMOVER & AUTO APPROVE -------------------- #
def is_forwarded(message: Message) -> bool:
    return bool(
        message.forward_from or 
        message.forward_from_chat or 
        message.forward_sender_name or 
        message.forward_date or 
        getattr(message, 'forward_origin', None)
    )

async def safe_copy_and_delete(
    msg: Message, 
    chat_id: int, 
    custom_caption: Optional[str] = None, 
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> Optional[Message]:
    """Clones the post to remove the forward tag without recursive stack overflows."""
    markup = reply_markup if reply_markup is not None else msg.reply_markup
    for _ in range(5):
        try:
            if msg.media:
                caption = custom_caption if custom_caption is not None else (msg.caption.html if msg.caption else "")
                sent = await msg.copy(
                    chat_id, 
                    caption=caption, 
                    parse_mode=ParseMode.HTML if custom_caption else None,
                    reply_markup=markup, 
                    disable_notification=True
                )
            else:
                text = custom_caption if custom_caption is not None else (msg.text.html if msg.text else "")
                sent = await app.send_message(
                    chat_id=chat_id, 
                    text=text, 
                    parse_mode=ParseMode.HTML if custom_caption else None,
                    reply_markup=markup, 
                    disable_notification=True, 
                    disable_web_page_preview=False
                )
            await asyncio.sleep(0.4)
            await msg.delete()
            return sent
        except Exception as e:
            if "FLOOD_WAIT" in str(e):
                wait_sec = int(re.search(r'(\d+)', str(e)).group(1)) + 2
                await asyncio.sleep(wait_sec)
                continue
            return None
    return None

# -------------------- AUTOMATIC CAPTION LINK & BUTTON DISPATCHER -------------------- #
async def process_channel_post_auto_buttons(client, message: Message):
    """
    Automatically detects '-https...' in post caption/text, cleans the caption,
    injects the link into the button template, and attaches buttons to the post.
    """
    settings = await get_channel_settings(message.chat.id)
    if not settings:
        return

    raw_text = message.caption or message.text or ""
    entities = message.caption_entities or message.entities

    # Check if user added a '-http...' link trigger
    has_trigger_link = bool(re.search(r'(?:^|\s)-(?:https?://)', raw_text, re.IGNORECASE))
    
    if has_trigger_link:
        html_text = get_html_text(raw_text, entities)
        extracted_link, cleaned_caption = extract_and_clean_caption_link(html_text)
        
        if extracted_link:
            template_data = await get_effective_template(message.chat.id)
            if template_data:
                template = template_data.get("template", "")
                font_style = template_data.get("font_style", "sim")
                
                # Replace {link} in the template with the caption link
                final_btn_text = re.sub(r"\{link\}", extracted_link, template, flags=re.IGNORECASE)
                keyboard = parse_buttons(final_btn_text, font_style=font_style)
                
                # Apply font to the remaining caption
                final_caption = apply_font_to_caption(cleaned_caption, font_style) if font_style != "normal" else cleaned_caption
                
                # If forward tag removal is active and message is forwarded, copy and delete
                if settings["forward_tag_removal"] and is_forwarded(message):
                    await asyncio.sleep(0.3)
                    await safe_copy_and_delete(message, message.chat.id, custom_caption=final_caption, reply_markup=keyboard)
                    return
                else:
                    # Edit the existing post in place
                    try:
                        if message.media:
                            await client.edit_message_caption(
                                chat_id=message.chat.id,
                                message_id=message.id,
                                caption=final_caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=keyboard
                            )
                        else:
                            await client.edit_message_text(
                                chat_id=message.chat.id,
                                message_id=message.id,
                                text=final_caption,
                                parse_mode=ParseMode.HTML,
                                reply_markup=keyboard
                            )
                        return
                    except Exception as err:
                        if "MESSAGE_NOT_MODIFIED" in str(err).upper() and keyboard:
                            try:
                                await client.edit_message_reply_markup(
                                    chat_id=message.chat.id,
                                    message_id=message.id,
                                    reply_markup=keyboard
                                )
                            except Exception:
                                pass
                        return

    # If no trigger link, perform normal forward tag removal if enabled
    if settings["forward_tag_removal"] and is_forwarded(message):
        await asyncio.sleep(0.3)
        await safe_copy_and_delete(message, message.chat.id)

@app.on_message(filters.channel & ~filters.service)
async def channel_post_listener(client, message: Message):
    await process_channel_post_auto_buttons(client, message)

@app.on_edited_message(filters.channel & ~filters.service)
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
