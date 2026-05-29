import re
import asyncio
from typing import Dict, Optional
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

# -------------------- FONT STYLES -------------------- #
FONT_S = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz', 'ᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢ'))
FONT_SM = dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789', 'ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿'))

def apply_sim(text: str) -> str:
    style = {"a": "𝖺", "b": "𝖻", "c": "𝖼", "d": "𝖽", "e": "𝖾", "f": "𝖿", "g": "𝗀", "h": "𝗁", "i": "𝗂", "j": "𝗃", "k": "𝗄", "l": "𝗅", "m": "𝗆", "n": "𝗇", "o": "𝗈", "p": "𝗉", "q": "𝗊", "r": "𝗋", "s": "𝗌", "t": "𝗍", "u": "𝗎", "v": "𝗏", "w": "𝗐", "x": "𝗑", "y": "𝗒", "z": "𝗓", "A": "𝖠", "B": "𝖡", "C": "𝖢", "D": "𝖣", "E": "𝖤", "F": "𝖥", "G": "𝖦", "H": "𝖧", "I": "𝖨", "J": "𝖩", "K": "𝖪", "L": "𝖫", "M": "𝖬", "N": "𝖭", "O": "𝖮", "P": "𝖯", "Q": "𝖰", "R": "𝖱", "S": "𝖲", "T": "𝖳", "U": "𝖴", "V": "𝖵", "W": "𝖶", "X": "𝖷", "Y": "𝖸", "Z": "𝖹"}
    return ''.join(style.get(c, c) for c in text)

def apply_san(text: str) -> str:
    style = {"a": "𝗮", "b": "𝗯", "c": "𝗰", "d": "𝗱", "e": "𝗲", "f": "𝗳", "g": "𝗴", "h": "𝗵", "i": "𝗶", "j": "𝗷", "k": "𝗸", "l": "𝗹", "m": "𝗺", "n": "𝗻", "o": "𝗼", "p": "𝗽", "q": "𝗾", "r": "𝗿", "s": "𝘀", "t": "𝘁", "u": "𝘂", "v": "𝘃", "w": "𝘄", "x": "𝘅", "y": "𝘆", "z": "𝘇", "A": "𝗔", "B": "𝗕", "C": "𝗖", "D": "𝗗", "E": "𝗘", "F": "𝗙", "G": "𝗚", "H": "𝗛", "I": "𝗜", "J": "𝗝", "K": "𝗞", "L": "𝗟", "M": "𝗠", "N": "𝗡", "O": "𝗢", "P": "𝗣", "Q": "𝗤", "R": "𝗥", "S": "𝗦", "T": "𝗧", "U": "𝗨", "V": "𝗩", "W": "𝗪", "X": "𝗫", "Y": "𝗬", "Z": "𝗭", "0": "𝟬", "1": "𝟭", "2": "𝟮", "3": "𝟯", "4": "𝟰", "5": "𝟱", "6": "𝟲", "7": "𝟳", "8": "𝟴", "9": "𝟵"}
    return ''.join(style.get(c, c) for c in text)

def apply_font(text: str, font_style: str) -> str:
    if font_style == 's': return ''.join(FONT_S.get(c, c) for c in text)
    elif font_style == 'sm': return ''.join(FONT_SM.get(c, c) for c in text)
    elif font_style in ['sim', 'a']: return apply_sim(text)
    elif font_style in ['san', 'b']: return apply_san(text)
    return text

# -------------------- DB HELPERS & TIME PARSER -------------------- #
def parse_time_to_seconds(time_str: str) -> int:
    if not time_str: return 1
    match = re.match(r'^(\d+)([smhd])$', time_str.strip().lower())
    if not match: return 1
    return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(match.group(2), 1)

async def add_auth_channel(chat_id: int, forward_tag: bool = True, auto_accept_time: str = "1s"):
    await authdb.update_one({"chat_id": str(chat_id)}, {"$set": {"chat_id": str(chat_id), "forward_tag_removal": forward_tag, "auto_accept_time": auto_accept_time, "auto_accept_seconds": parse_time_to_seconds(auto_accept_time)}}, upsert=True)

async def remove_auth_channel(chat_id: int): await authdb.delete_one({"chat_id": str(chat_id)})
async def is_channel_authed(chat_id: int) -> bool: return bool(await authdb.find_one({"chat_id": str(chat_id)}))

async def get_channel_settings(chat_id: int) -> Optional[Dict]:
    data = await authdb.find_one({"chat_id": str(chat_id)})
    if data: return {"forward_tag_removal": data.get("forward_tag_removal", True), "auto_accept_time": data.get("auto_accept_time", "1s"), "auto_accept_seconds": data.get("auto_accept_seconds", 1)}
    return None

async def save_button_template(user_id: int, template: str, font_style: str = "sim"):
    await btn_templatedb.update_one({"user_id": str(user_id)}, {"$set": {"template": template, "font_style": font_style}}, upsert=True)

async def get_button_template(user_id: int) -> Optional[Dict]:
    return await btn_templatedb.find_one({"user_id": str(user_id)})

async def delete_button_template(user_id: int):
    await btn_templatedb.delete_one({"user_id": str(user_id)})

# -------------------- AUTH COMMANDS -------------------- #
@app.on_message(filters.command(["auth"]))
async def auth_channel_cmd(client, message: Message):
    args = message.text.split()
    forward_tag, auto_accept_time, chat_id = True, "1s", None
    if "-f" in args and args.index("-f") + 1 < len(args): forward_tag = args[args.index("-f") + 1].lower() in ["on", "true", "1"]
    if "-ac" in args and args.index("-ac") + 1 < len(args): auto_accept_time = args[args.index("-ac") + 1]
    
    if message.reply_to_message and message.reply_to_message.forward_from_chat: chat_id = message.reply_to_message.forward_from_chat.id
    elif len(args) >= 2:
        try: chat_id = (await client.get_chat(args[1])).id if args[1].startswith("@") else int(args[1])
        except Exception as e: return await message.reply_text(f"❌ Invalid channel! Error: {e}")
            
    if not chat_id: return await message.reply_text("❌ Usage: `/auth <channel_id> -f on/off -ac 1s`")
    
    try:
        priv = getattr(await client.get_chat_member(chat_id, "me"), "privileges", None)
        if not priv or not getattr(priv, "can_post_messages", False): return await message.reply_text("❌ Bot needs post messages rights.")
    except Exception as e: return await message.reply_text(f"⚠️ Error: {e}")
    
    await add_auth_channel(chat_id, forward_tag, auto_accept_time)
    await message.reply_text(f"✅ **Channel Authorized!**\nID: `{chat_id}` | Fwd Tag: {'ON' if forward_tag else 'OFF'} | Auto-Accept: {auto_accept_time}")

@app.on_message(filters.command(["unauth"]))
async def unauth_channel_cmd(client, message: Message):
    chat_id = None
    if len(message.command) == 2:
        try: chat_id = (await client.get_chat(message.command[1])).id if message.command[1].startswith("@") else int(message.command[1])
        except: return await message.reply_text("❌ Invalid channel!")
    elif message.reply_to_message and message.reply_to_message.forward_from_chat: chat_id = message.reply_to_message.forward_from_chat.id
    else: return await message.reply_text("❌ Usage: /unauth <channel_id>")
    await remove_auth_channel(chat_id)
    await message.reply_text(f"✅ Un-Authorized: `{chat_id}`")

# -------------------- SMART BUTTON PARSER (NO FONT ON BUTTONS) -------------------- #
def create_button(text: str, url: str, style=RED_STYLE):
    try: return InlineKeyboardButton(text, url=url, style=style)
    except TypeError: return InlineKeyboardButton(text, url=url)

def parse_buttons(text: str, font_style: str = "sim") -> Optional[InlineKeyboardMarkup]:
    keyboard = []
    for line in text.strip().splitlines():
        btns = []
        for match in re.finditer(r"\[([^\]]+?)\s*\+\s*(https?://[^\s\]]+)\]\s*([rgbRGB]?)", line):
            label = match.group(1).strip()
            link = match.group(2).strip()
            color_code = match.group(3).strip().lower()
            
            # Button text ko touch nahi karenge, jo template me hai wahi rahega
            color_map = {"r": RED_STYLE, "g": GREEN_STYLE, "b": BLUE_STYLE}
            btn_style = color_map.get(color_code, RED_STYLE)
            btns.append(create_button(label, link, style=btn_style))
        if btns: keyboard.append(btns)
    return InlineKeyboardMarkup(keyboard) if keyboard else None

# -------------------- CAPTION FONT UPDATER (PRO LOGIC) -------------------- #
EXCLUDED_CAPTION_LINE = "❖ 𝐌ᴧᴅє 𝐁ɣ ➛ ˹ SyntaxRealm.t.me ˼"

def apply_font_to_caption(caption: str, font_style: str) -> str:
    if not caption or font_style == "normal":
        return caption

    lines = caption.split('\n')
    new_lines = []
    
    for line in lines:
        # Specific line ko skip karna hai
        if EXCLUDED_CAPTION_LINE in line:
            new_lines.append(line)
            continue
            
        placeholders = {}
        counter = 0
        
        def replace_with_placeholder(match):
            nonlocal counter
            placeholder = f"@@{counter}@@"
            placeholders[placeholder] = match.group(0)
            counter += 1
            return placeholder
            
        # URLs aur HTML tags ko protect karna hai taki unka font change na ho
        url_pattern = r'(https?://[^\s\]\)\*]+|tg://[^\s\]\)\*]+|t\.me/[^\s\]\)\*]+)'
        html_tag_pattern = r'<[^>]+>'
        
        temp_line = re.sub(url_pattern, replace_with_placeholder, line)
        temp_line = re.sub(html_tag_pattern, replace_with_placeholder, temp_line)
        
        # Baki bache text par font apply karo
        styled_line = apply_font(temp_line, font_style)
        
        # Wapas placeholders ko original text se replace karo
        for ph, original in placeholders.items():
            styled_line = styled_line.replace(ph, original)
            
        new_lines.append(styled_line)
        
    return '\n'.join(new_lines)

# -------------------- AUTO BUTTON SET (/abset) -------------------- #
@app.on_message(filters.command(["ab", "abset", "ab -s"]))
async def set_auto_button_template(client, message: Message):
    font_style = "sim"
    text = message.text or message.caption or ""
    
    font_match = re.search(r"-f\s+(\w+)", text)
    if font_match:
        font_style = font_match.group(1).lower()
        if font_style not in ["sim", "san", "s", "sm", "normal"]: font_style = "sim"
            
    template_text = ""
    if message.reply_to_message and message.reply_to_message.text:
        template_text = message.reply_to_message.text
    else:
        template_text = re.sub(r"^/(ab|abset|ab\s*-s)\s*", "", text, flags=re.IGNORECASE)
        template_text = re.sub(r"-f\s+\w+", "", template_text, flags=re.IGNORECASE).strip()
        
    if not template_text: return await message.reply_text("❌ Bhai template text toh de! Reply to a message or type it after the command.")
        
    keyboard = parse_buttons(template_text, font_style=font_style)
    if not keyboard: return await message.reply_text("❌ Koi valid button nahi mila! Format: `[Text + URL] r`")
        
    await save_button_template(message.from_user.id, template_text, font_style)
    
    preview_text = template_text.replace("{link}", "https://t.me/PreviewDemo")
    preview_keyboard = parse_buttons(preview_text, font_style=font_style)
    
    font_display = {"sim": "Sim (Serif)", "san": "San (Bold)", "s": "Small Caps", "sm": "Small+Num", "normal": "Default"}
    
    await message.reply_text(
        f"✅ **Template Set Ho Gaya Bro!**\n"
        f"🎨 **Font:** `{font_display.get(font_style, font_style)}`\n"
        f"👇 **Niche Preview Dekh Le:**",
        reply_markup=preview_keyboard
    )

@app.on_message(filters.command(["absee", "abseen"]))
async def see_auto_button_template(client, message: Message):
    data = await get_button_template(message.from_user.id)
    if not data: return await message.reply_text("❌ Koi template set nahi hai bhai! Pehle `/abset` kar.")
        
    template_text, font_style = data["template"], data.get("font_style", "sim")
    preview_text = template_text.replace("{link}", "https://t.me/PreviewDemo")
    preview_keyboard = parse_buttons(preview_text, font_style=font_style)
    
    font_display = {"sim": "Sim (Serif)", "san": "San (Bold)", "s": "Small Caps", "sm": "Small+Num", "normal": "Default"}
    
    await message.reply_text(
        f"📋 **Tera Set Kiya Hua Template:**\n`{template_text}`\n\n"
        f"🎨 **Font:** `{font_display.get(font_style, font_style)}`\n"
        f"👇 **Preview:**",
        reply_markup=preview_keyboard
    )

@app.on_message(filters.command(["abrm"]))
async def remove_auto_button_template(client, message: Message):
    await delete_button_template(message.from_user.id)
    await message.reply_text("🗑️ Template remove kar diya bhai!")

# -------------------- APPLY TEMPLATE (/au) -------------------- #
@app.on_message(filters.command(["au", "acbapply"]))
async def apply_auto_button_cmd(client, message: Message):
    template_data = await get_button_template(message.from_user.id)
    if not template_data: return await message.reply_text("❌ Bhai pehle `/abset` se template set kar!")
        
    template, font_style = template_data["template"], template_data.get("font_style", "sim")
    args = message.command[1:]
    target_link, replacement_link = None, None
    
    if message.reply_to_message:
        replied_text = message.reply_to_message.text or message.reply_to_message.caption or ""
        url_match = re.search(r"(https?://t\.me/\S+)", replied_text)
        if url_match: replacement_link = url_match.group(1)
        if args and args[0].startswith("http"): target_link = args[0]
    else:
        if len(args) >= 2: target_link, replacement_link = args[0], args[1]
        elif len(args) == 1: target_link = args[0]
            
    if not target_link: return await message.reply_text("❌ Usage: Reply to link with `/au <target_post_link>`")
        
    public_match = re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", target_link)
    private_match = re.match(r"https?://t\.me/c/(-?\d+)/(\d+)", target_link)
    
    if public_match:
        try: channel_id, msg_id = (await client.get_chat(public_match.group(1))).id, int(public_match.group(2))
        except Exception as e: return await message.reply_text(f"❌ Channel nahi mila: {e}")
    elif private_match: channel_id, msg_id = int("-100" + private_match.group(1)), int(private_match.group(2))
    else: return await message.reply_text("❌ Invalid target link format!")
        
    if not await is_channel_authed(channel_id): return await message.reply_text("❌ Channel authorized nahi hai.")
        
    if not replacement_link:
        try:
            chat = await client.get_chat(channel_id)
            replacement_link = f"https://t.me/{chat.username}" if chat.username else "https://t.me/YourChannel"
        except: replacement_link = "https://t.me/YourChannel"
            
    final_text = re.sub(r"\{link\}", replacement_link, template, flags=re.IGNORECASE)
    keyboard = parse_buttons(final_text, font_style=font_style)
    if not keyboard: return await message.reply_text("❌ Buttons parse nahi hue!")
        
    try:
        # 1. Pehle buttons edit karenge
        await client.edit_message_reply_markup(chat_id=channel_id, message_id=msg_id, reply_markup=keyboard)
        
        # 2. Phir Caption ko Smartly Update karenge
        target_msg = await client.get_messages(channel_id, msg_id)
        if target_msg.caption and font_style != "normal":
            new_caption = apply_font_to_caption(target_msg.caption, font_style)
            if new_caption != target_msg.caption:
                await client.edit_message_caption(
                    chat_id=channel_id, 
                    message_id=msg_id, 
                    caption=new_caption
                )
                
        await message.reply_text(f"✅ **Pro Level Buttons & Caption Set!**\n🔥 Font: `{font_style}`")
    except Exception as e: await message.reply_text(f"⚠️ Edit fail: {e}")

# -------------------- CHANGE BUTTON (/cb) -------------------- #
@app.on_message(filters.command(["cb"]))
async def change_button_with_link(client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.text: return await message.reply_text("❌ Reply to a button-text message with /cb <post_link>")
    args = message.command
    if len(args) < 2: return await message.reply_text("❌ Usage: `/cb <link>`")
    
    link = args[1]
    public_match = re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", link)
    private_match = re.match(r"https?://t\.me/c/(-?\d+)/(\d+)", link)
    
    if public_match:
        try: channel_id, msg_id = (await client.get_chat(public_match.group(1))).id, int(public_match.group(2))
        except Exception as e: return await message.reply_text(f"❌ Channel nahi mila: {e}")
    elif private_match: channel_id, msg_id = int("-100" + private_match.group(1)), int(private_match.group(2))
    else: return await message.reply_text("❌ Invalid link format!")
    
    if not await is_channel_authed(channel_id): return await message.reply_text("❌ Channel authorized nahi hai.")
    
    keyboard = parse_buttons(message.reply_to_message.text, font_style="normal")
    if not keyboard: return await message.reply_text("❌ Invalid button format!")
    
    try:
        await client.edit_message_reply_markup(chat_id=channel_id, message_id=msg_id, reply_markup=keyboard)
        await message.reply_text(f"✅ Buttons updated with custom colors!")
    except Exception as e: await message.reply_text(f"⚠️ Edit fail: {e}")

# -------------------- FORWARD TAG REMOVER & AUTO APPROVE -------------------- #
def is_forwarded(message: Message) -> bool:
    return bool(message.forward_from or message.forward_from_chat or message.forward_sender_name or message.forward_date or getattr(message, 'forward_origin', None))

async def safe_copy_and_delete(msg: Message, chat_id: int):
    try:
        sent = await msg.copy(chat_id, reply_markup=msg.reply_markup, disable_notification=True) if msg.web_page or msg.caption else await app.send_message(chat_id=chat_id, text=msg.text, entities=msg.entities, reply_markup=msg.reply_markup, disable_notification=True, disable_web_page_preview=False)
        await asyncio.sleep(0.5)
        await msg.delete()
        return sent
    except Exception as e:
        if "FLOOD_WAIT" in str(e): await asyncio.sleep(int(re.search(r'(\d+)', str(e)).group(1)) + 2); return await safe_copy_and_delete(msg, chat_id)
        return None

@app.on_message(filters.channel & ~filters.service)
async def remove_forward_tag_handler(client, message: Message):
    settings = await get_channel_settings(message.chat.id)
    if settings and settings["forward_tag_removal"] and is_forwarded(message):
        await asyncio.sleep(0.3)
        await safe_copy_and_delete(message, message.chat.id)

@app.on_chat_join_request()
async def auto_approve_join_request(client, request: ChatJoinRequest):
    settings = await get_channel_settings(request.chat.id)
    if settings:
        await asyncio.sleep(settings["auto_accept_seconds"])
        try: await client.approve_chat_join_request(chat_id=request.chat.id, user_id=request.from_user.id)
        except: pass
