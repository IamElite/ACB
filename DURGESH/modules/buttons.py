import re
import asyncio
from typing import Dict
from pyrogram import filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton
)
from pyrogram.enums import ParseMode
from DURGESH import app
from DURGESH.database import db

authdb = db.auth_channels

# -------------------- AUTH HELPERS -------------------- #

async def add_auth_channel(chat_id: int):
    await authdb.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {"chat_id": str(chat_id)}},
        upsert=True
    )

async def remove_auth_channel(chat_id: int):
    await authdb.delete_one({"chat_id": str(chat_id)})

async def is_channel_authed(chat_id: int) -> bool:
    data = await authdb.find_one({"chat_id": str(chat_id)})
    return bool(data)

# -------------------- AUTH COMMANDS -------------------- #

@app.on_message(filters.command(["auth"]))
async def auth_channel_cmd(client, message: Message):
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
        return await message.reply_text("❌ Usage: /auth <channel_id> or reply to a channel forwarded post.")
    
    try:
        member = await client.get_chat_member(chat_id, "me")
        priv = getattr(member, "privileges", None)
        if not priv or not getattr(priv, "can_post_messages", False):
            return await message.reply_text("❌ Bot must be admin with post messages rights in that channel.")
    except Exception as e:
        return await message.reply_text(f"⚠️ Error: {e}")
    
    await add_auth_channel(chat_id)
    await message.reply_text(f"✅ Authorized channel: `{chat_id}`", parse_mode=ParseMode.MARKDOWN)

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

    text = "✅ Authorized Channels:\n\n"
    for i, doc in enumerate(channels, start=1):
        chat_id = int(doc["chat_id"])
        try:
            chat = await client.get_chat(chat_id)
            name = chat.title or "Unknown"
            text += f"**{i}.** {name} (`{chat_id}`)\n"
        except:
            text += f"**{i}.** `{chat_id}` (not accessible)\n"

    await message.reply_text(text)


# -------------------- BUTTON PARSER -------------------- #

def parse_buttons(text: str) -> InlineKeyboardMarkup | None:
    keyboard = []
    lines = text.strip().splitlines()

    for line in lines:
        btns = []
        matches = re.findall(r"\[([^\]]+?)\s*\+\s*(https?://\S+)\]", line)
        for label, link in matches:
            btns.append(InlineKeyboardButton(label.strip(), url=link.strip()))
        if btns:
            keyboard.append(btns)

    return InlineKeyboardMarkup(keyboard) if keyboard else None


# -------------------- CHANGE BUTTON -------------------- #

@app.on_message(filters.command(["cb"]))
async def change_button_with_link(client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.text:
        return await message.reply_text("❌ Reply to a button-text message with /cb <post_link>")

    if len(message.command) != 2:
        return await message.reply_text("❌ Usage: /cb <channel_post_link>")

    link = message.command[1]
    
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

    keyboard = parse_buttons(message.reply_to_message.text)
    if not keyboard:
        return await message.reply_text("❌ Invalid button format!\n\n📝 Format:\n[Text + Link]\n[Another + Link]")

    try:
        await client.edit_message_reply_markup(
            chat_id=channel_id,
            message_id=msg_id,
            reply_markup=keyboard
        )
        await message.reply_text("✅ Buttons updated successfully!")
    except Exception as e:
        await message.reply_text(f"⚠️ Failed to edit message: {e}")


# -------------------- FORWARD TAG REMOVER -------------------- #

def is_forwarded(message: Message) -> bool:
    """Check if message is forwarded using all possible indicators"""
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
        # Copy message based on its type
        if msg.text:
            sent = await msg.copy(
                chat_id,
                caption=None,
                reply_markup=msg.reply_markup,
                disable_notification=True
            )
        elif msg.caption:
            sent = await msg.copy(
                chat_id,
                reply_markup=msg.reply_markup,
                disable_notification=True
            )
        else:
            # For media without caption
            sent = await msg.copy(
                chat_id,
                reply_markup=msg.reply_markup,
                disable_notification=True
            )
        
        # Delete original forwarded message
        await asyncio.sleep(0.5)  # Small delay before deletion
        await msg.delete()
        
        return sent
        
    except Exception as e:
        error_msg = str(e)
        
        # Handle flood wait
        if "FLOOD_WAIT" in error_msg or "FloodWait" in error_msg:
            try:
                wait = int(re.search(r'(\d+)', error_msg).group(1))
                print(f"⏳ FloodWait: Waiting {wait} seconds...")
                await asyncio.sleep(wait + 2)
                return await safe_copy_and_delete(msg, chat_id)
            except:
                pass
        
        # Handle other errors
        print(f"❌ Error in safe_copy_and_delete: {error_msg}")
        return None


@app.on_message(filters.channel & ~filters.service)
async def remove_forward_tag_handler(client, message: Message):
    """Automatically remove forward tag from authorized channels"""
    
    # Check if channel is authorized
    if not await is_channel_authed(message.chat.id):
        return
    
    # Check if message is forwarded
    if not is_forwarded(message):
        return
    
    # Small delay to ensure message is fully received
    await asyncio.sleep(0.3)
    
    # Copy and delete the forwarded message
    await safe_copy_and_delete(message, message.chat.id)
