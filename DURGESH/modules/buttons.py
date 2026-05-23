import re
import asyncio
from typing import Dict
from pyrogram import filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
)
from pyrogram.enums import ParseMode
from DURGESH import app
from DURGESH.database import db

authdb = db.auth_channels

# -------------------- TIME PARSER -------------------- #

def parse_time_to_seconds(time_str: str) -> int:
    """Convert time string like 1s, 1m, 1h, 1d to seconds"""
    if not time_str:
        return 1  # default 1 second
    
    time_str = time_str.strip().lower()
    match = re.match(r'^(\d+)([smhd])$', time_str)
    
    if not match:
        return 1
    
    value = int(match.group(1))
    unit = match.group(2)
    
    conversions = {
        's': 1,           # seconds
        'm': 60,          # minutes
        'h': 3600,        # hours
        'd': 86400        # days
    }
    
    return value * conversions.get(unit, 1)

# -------------------- AUTH HELPERS -------------------- #

async def add_auth_channel(chat_id: int, forward_tag: bool = True, auto_accept_time: str = "1s"):
    """Add/Update authorized channel with settings"""
    await authdb.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {
            "chat_id": str(chat_id),
            "forward_tag_removal": forward_tag,
            "auto_accept_time": auto_accept_time,
            "auto_accept_seconds": parse_time_to_seconds(auto_accept_time)
        }},
        upsert=True
    )

async def remove_auth_channel(chat_id: int):
    await authdb.delete_one({"chat_id": str(chat_id)})

async def is_channel_authed(chat_id: int) -> bool:
    data = await authdb.find_one({"chat_id": str(chat_id)})
    return bool(data)

async def get_channel_settings(chat_id: int) -> Dict:
    """Get channel settings"""
    data = await authdb.find_one({"chat_id": str(chat_id)})
    if data:
        return {
            "forward_tag_removal": data.get("forward_tag_removal", True),
            "auto_accept_time": data.get("auto_accept_time", "1s"),
            "auto_accept_seconds": data.get("auto_accept_seconds", 1)
        }
    return None

# -------------------- AUTH COMMANDS -------------------- #

@app.on_message(filters.command(["auth"]))
async def auth_channel_cmd(client, message: Message):
    """
    Usage: 
    /auth <channel_id> -f on/off -ac 1s/1m/1h/1d
    OR reply to forwarded channel message
    """
    args = message.text.split()
    forward_tag = True  
    auto_accept_time = "1s"  
    chat_id = None
    
    if "-f" in args:
        idx = args.index("-f")
        if idx + 1 < len(args):
            forward_tag = args[idx + 1].lower() in ["on", "true", "1"]
    
    if "-ac" in args:
        idx = args.index("-ac")
        if idx + 1 < len(args):
            auto_accept_time = args[idx + 1]
    
    if message.reply_to_message and message.reply_to_message.forward_from_chat:
        chat_id = message.reply_to_message.forward_from_chat.id
    elif len(args) >= 2:
        try:
            if args[1].startswith("@"):
                chat = await client.get_chat(args[1])
                chat_id = chat.id
            elif args[1].lstrip('-').isdigit():
                chat_id = int(args[1])
        except (ValueError, Exception) as e:
            return await message.reply_text(f"❌ Invalid channel_id or username!\nError: {e}")
    
    if not chat_id:
        return await message.reply_text(
            "❌ **Usage:**\n"
            "`/auth <channel_id> -f on/off -ac 1s`\n\n"
            "**OR** reply to a forwarded channel message\n\n"
            "**Flags:**\n"
            "`-f` : Forward tag removal (on/off) - default: on\n"
            "`-ac` : Auto-accept time (1s/1m/1h/1d) - default: 1s"
        )
    
    try:
        member = await client.get_chat_member(chat_id, "me")
        priv = getattr(member, "privileges", None)
        if not priv or not getattr(priv, "can_post_messages", False):
            return await message.reply_text("❌ Bot must be admin with post messages rights in that channel.")
    except Exception as e:
        return await message.reply_text(f"⚠️ Error: {e}")
    
    await add_auth_channel(chat_id, forward_tag, auto_accept_time)
    
    await message.reply_text(
        f"✅ **Channel Authorized!**\n\n"
        f"📌 **Channel ID:** `{chat_id}`\n"
        f"🔄 **Forward Tag Removal:** {'✅ ON' if forward_tag else '❌ OFF'}\n"
        f"⏱️ **Auto-Accept Time:** {auto_accept_time} ({parse_time_to_seconds(auto_accept_time)}s)\n\n"
        f"💡 To update settings, run /auth again with new values!",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command(["unauth"]))
async def unauth_channel_cmd(client, message: Message):
    if len(message.command) == 2:
        try:
            if message.command[1].startswith("@"):
                chat = await client.get_chat(message.command[1])
                chat_id = chat.id
            else:
                chat_id = int(message.command[1])
        except (ValueError, Exception):
            return await message.reply_text("❌ Invalid channel_id or username!")
    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        chat_id = message.reply_to_message.forward_from_chat.id
    else:
        return await message.reply_text("❌ Usage: /unauth <channel_id> or reply to a channel forwarded post.")
    
    await remove_auth_channel(chat_id)
    await message.reply_text(f"✅ Un-Authorized channel: `{chat_id}`", parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command(["authlist", "al"]))
async def authlist_handler(client, message: Message):
    cursor = authdb.find({})
    channels = [doc async for doc in cursor]

    if not channels:
        return await message.reply_text("⚠️ Abhi tak koi bhi channel authorize nahi hai.")

    text = "✅ **Authorized Channels:**\n\n"
    for i, doc in enumerate(channels, start=1):
        chat_id = int(doc["chat_id"])
        fwd_tag = "ON" if doc.get("forward_tag_removal", True) else "OFF"
        ac_time = doc.get("auto_accept_time", "1s")
        
        try:
            chat = await client.get_chat(chat_id)
            name = chat.title or "Unknown"
            text += f"**{i}.** {name}\n"
            text += f"   ├ ID: `{chat_id}`\n"
            text += f"   ├ Forward Tag: {fwd_tag}\n"
            text += f"   └ Auto-Accept: {ac_time}\n\n"
        except:
            text += f"**{i}.** `{chat_id}` (not accessible)\n\n"

    await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


# -------------------- BUTTON HELPER & PARSER -------------------- #

def create_button(text: str, url: str, style: str = "red"):
    """Create button with fallback for unsupported 'style' parameter"""
    try:
        # Kurigram latest version might support 'style' for colors
        return InlineKeyboardButton(text, url=url, style=style)
    except TypeError:
        # Agar support nahi karta toh simple default button bana dega (Crash nahi hoga)
        return InlineKeyboardButton(text, url=url)

def parse_buttons(text: str, style: str = "red") -> InlineKeyboardMarkup | None:
    keyboard = []
    lines = text.strip().splitlines()

    for line in lines:
        btns = []
        matches = re.findall(r"\[([^\]]+?)\s*\+\s*(https?://\S+)\]", line)
        for label, link in matches:
            btns.append(create_button(label.strip(), link.strip(), style))
        if btns:
            keyboard.append(btns)

    return InlineKeyboardMarkup(keyboard) if keyboard else None


# -------------------- CHANGE BUTTON -------------------- #

@app.on_message(filters.command(["cb"]))
async def change_button_with_link(client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.reply_text("❌ Reply to a button-text message with /cb <post_link> [color]")

    args = message.command
    if len(args) < 2:
        return await message.reply_text(
            "❌ **Usage:** `/cb <link> [color]`\n\n"
            "**Colors:** `red` (r), `green` (g), `blue` (b)\n"
            "**Default:** `red`"
        )

    link = args[1]
    
    # Color Logic (Default: red)
    color_arg = args[2].lower() if len(args) > 2 else "red"
    color_map = {
        "r": "red", "red": "red",
        "g": "green", "green": "green",
        "b": "blue", "blue": "blue"
    }
    btn_style = color_map.get(color_arg, "red")

    public_match = re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", link)
    private_match = re.match(r"https?://t\.me/c/(-?\d+)/(\d+)", link)

    if public_match:
        chat_username = public_match.group(1)
        msg_id = int(public_match.group(2))
        try:
            chat = await client.get_chat(chat_username)
            channel_id = chat.id
        except Exception as e:
            return await message.reply_text(f"❌ Could not find the public channel: {e}")
    elif private_match:
        channel_id = int("-100" + private_match.group(1))
        msg_id = int(private_match.group(2))
    else:
        return await message.reply_text("❌ Invalid link format!\nUse: `https://t.me/channelname/123` or `https://t.me/c/.../123`")

    if not await is_channel_authed(channel_id):
        return await message.reply_text("❌ This channel is not authorized. Use /auth first.")

    keyboard = parse_buttons(message.reply_to_message.text, style=btn_style)
    if not keyboard:
        return await message.reply_text("❌ Invalid button format!\n\n📝 Format:\n[Text + Link]\n[Another + Link]")

    try:
        await client.edit_message_reply_markup(
            chat_id=channel_id,
            message_id=msg_id,
            reply_markup=keyboard
        )
        await message.reply_text(f"✅ Buttons updated successfully! (Color: {btn_style})")
    except Exception as e:
        await message.reply_text(f"⚠️ Failed to edit message: {e}")


# -------------------- FORWARD TAG REMOVER -------------------- #

def is_forwarded(message: Message) -> bool:
    """Check if message is forwarded"""
    return bool(
        message.forward_from or 
        message.forward_from_chat or 
        message.forward_sender_name or
        message.forward_date or
        getattr(message, 'forward_origin', None)
    )

async def safe_copy_and_delete(msg: Message, chat_id: int):
    """Copy message without forward tag and delete original"""
    try:
        web_preview = None
        if msg.web_page:
            web_preview = msg.web_page
        
        if msg.text:
            if web_preview:
                sent = await msg.copy(
                    chat_id,
                    reply_markup=msg.reply_markup,
                    disable_notification=True
                )
            else:
                sent = await app.send_message(
                    chat_id=chat_id,
                    text=msg.text,
                    entities=msg.entities,
                    reply_markup=msg.reply_markup,
                    disable_notification=True,
                    disable_web_page_preview=False
                )
        elif msg.caption:
            sent = await msg.copy(
                chat_id,
                reply_markup=msg.reply_markup,
                disable_notification=True
            )
        else:
            sent = await msg.copy(
                chat_id,
                reply_markup=msg.reply_markup,
                disable_notification=True
            )
        
        await asyncio.sleep(0.5)
        await msg.delete()
        
        return sent
        
    except Exception as e:
        error_msg = str(e)
        
        if "FLOOD_WAIT" in error_msg or "FloodWait" in error_msg:
            try:
                wait = int(re.search(r'(\d+)', error_msg).group(1))
                print(f"⏳ FloodWait: Waiting {wait} seconds...")
                await asyncio.sleep(wait + 2)
                return await safe_copy_and_delete(msg, chat_id)
            except:
                pass
        
        print(f"❌ Error in safe_copy_and_delete: {error_msg}")
        return None


@app.on_message(filters.channel & ~filters.service)
async def remove_forward_tag_handler(client, message: Message):
    """Automatically remove forward tag from authorized channels"""
    settings = await get_channel_settings(message.chat.id)
    if not settings:
        return
    
    if not settings["forward_tag_removal"]:
        return
    
    if not is_forwarded(message):
        return
    
    await asyncio.sleep(0.3)
    await safe_copy_and_delete(message, message.chat.id)


# -------------------- AUTO APPROVE JOIN REQUESTS -------------------- #

@app.on_chat_join_request()
async def auto_approve_join_request(client, request: ChatJoinRequest):
    """Auto approve join requests after specified time"""
    chat_id = request.chat.id
    settings = await get_channel_settings(chat_id)
    
    if not settings:
        return
    
    wait_time = settings["auto_accept_seconds"]
    await asyncio.sleep(wait_time)
    
    try:
        await client.approve_chat_join_request(
            chat_id=chat_id,
            user_id=request.from_user.id
        )
        print(f"✅ Approved join request from {request.from_user.id} in {chat_id} after {wait_time}s")
    except Exception as e:
        print(f"❌ Failed to approve join request: {e}")
