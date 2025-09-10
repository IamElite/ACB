import re
import asyncio
from typing import Dict, Tuple
from pyrogram import filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    MessageOriginChannel
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
            chat_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("❌ Invalid channel_id!")
    elif message.reply_to_message and isinstance(message.reply_to_message.forward_origin, MessageOriginChannel):
        chat_id = message.reply_to_message.forward_origin.chat.id
    else:
        return await message.reply_text("❌ Usage: /auth <channel_id> or reply to a channel forwarded post.")
    try:
        member = await client.get_chat_member(chat_id, "me")
        priv = getattr(member, "privileges", None)
        if not priv or not getattr(priv, "can_edit_messages", False):
            return await message.reply_text("❌ Bot must be admin with edit messages rights in that channel.")
    except Exception as e:
        return await message.reply_text(f"⚠️ Error: {e}")
    await add_auth_channel(chat_id)
    await message.reply_text(f"✅ Authorized channel: `{chat_id}`", parse_mode=ParseMode.MARKDOWN)

@app.on_message(filters.command(["unauth"]))
async def unauth_channel_cmd(client, message: Message):
    if len(message.command) == 2:
        try:
            chat_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("❌ Invalid channel_id!")
    elif message.reply_to_message and isinstance(message.reply_to_message.forward_origin, MessageOriginChannel):
        chat_id = message.reply_to_message.forward_origin.chat.id
    else:
        return await message.reply_text("❌ Usage: /unauth <channel_id> or reply to a channel forwarded post.")
    await remove_auth_channel(chat_id)
    await message.reply_text(f"✅ Un-Authorized channel: `{chat_id}`", parse_mode=ParseMode.MARKDOWN)

# -------------------- BUTTON PARSER -------------------- #

def parse_buttons(text: str):
    keyboard = []
    for line in text.strip().splitlines():
        btns = []
        matches = re.findall(r"\[([^+\]]+?)\s*\+\s*(https?://[^\]\s]+)\]", line)
        for label, link in matches:
            btns.append(InlineKeyboardButton(label.strip(), url=link.strip()))
        if btns:
            keyboard.append(btns)
    return InlineKeyboardMarkup(keyboard) if keyboard else None

# -------------------- CHANGE BUTTON -------------------- #

pending_changes: Dict[int, Tuple[int, int]] = {}

@app.on_message(filters.command(["changebutton", "cb"]))
async def change_button_start(client, message: Message):
    if not message.reply_to_message or not isinstance(message.reply_to_message.forward_origin, MessageOriginChannel):
        return await message.reply_text("❌ Reply to a channel forwarded post to change its buttons.")
    origin = message.reply_to_message.forward_origin
    channel_id = origin.chat.id
    msg_id = origin.message_id
    if not await is_channel_authed(channel_id):
        return await message.reply_text("❌ This channel is not authorized. Use /auth first.")
    pending_changes[message.from_user.id] = (channel_id, msg_id)
    await message.reply_text(
        "📝 Reply to the same forwarded post with new buttons:\n\n"
        "[Text + https://link]\n"
        "[Another + https://link] [Third + https://link]"
    )

@app.on_message(filters.text)
async def change_button_receive(client, message: Message):
    uid = message.from_user.id
    if uid not in pending_changes:
        return
    if not message.reply_to_message or not isinstance(message.reply_to_message.forward_origin, MessageOriginChannel):
        return await message.reply_text("❌ Please reply to the same forwarded post with the new buttons.")
    channel_id, msg_id = pending_changes.get(uid)
    origin = message.reply_to_message.forward_origin
    orig_chat = origin.chat.id
    orig_msg_id = origin.message_id
    if orig_chat != channel_id or orig_msg_id != msg_id:
        pending_changes.pop(uid, None)
        return await message.reply_text("❌ Wrong post! Start again with /cb.")
    keyboard = parse_buttons(message.text)
    if not keyboard:
        return await message.reply_text("❌ Invalid button format! Use: [Text + https://link]")
    pending_changes.pop(uid, None)
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

async def safe_copy_and_delete(msg: Message, chat_id: int, cap=None):
    try:
        await msg.copy(
            int(chat_id),
            caption=cap,
            parse_mode=ParseMode.HTML,
            reply_markup=msg.reply_markup
        )
        await msg.delete()
    except Exception as e:
        if "FLOOD_WAIT" in str(e):
            wait = int(str(e).split("wait ")[1].split()[0])
            await asyncio.sleep(wait)
            try:
                await msg.copy(
                    int(chat_id),
                    caption=cap,
                    parse_mode=ParseMode.HTML,
                    reply_markup=msg.reply_markup
                )
                await msg.delete()
            except:
                pass
        else:
            print("safe_copy_and_delete failed:", e)
    await asyncio.sleep(1)

@app.on_message(filters.channel)
async def remove_forward_tag_handler(client, message: Message):
    # Normal forward ya via bot dono detect karo
    if not message.forward_origin and not message.via_bot:
        return
    channel_id = message.chat.id
    if not await is_channel_authed(channel_id):
        return
    cap = message.caption if getattr(message, "caption", None) else None
    await safe_copy_and_delete(message, channel_id, cap=cap)
