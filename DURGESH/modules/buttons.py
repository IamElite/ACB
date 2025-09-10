import re
from typing import Dict, Tuple
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from DURGESH import app
from DURGESH.database import db

authdb = db.auth_channels

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

@app.on_message(filters.command(["auth"]))
async def auth_channel_cmd(client, message: Message):
    if len(message.command) == 2:
        try:
            chat_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("❌ Invalid channel_id!")
    elif message.reply_to_message and message.reply_to_message.forward_origin:
        chat_id = message.reply_to_message.forward_origin.chat.id
    else:
        return await message.reply_text("❌ Usage: /auth <channel_id> or reply to a forwarded channel message.")
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
    elif message.reply_to_message and message.reply_to_message.forward_origin:
        chat_id = message.reply_to_message.forward_origin.chat.id
    else:
        return await message.reply_text("❌ Usage: /unauth <channel_id> or reply to a forwarded channel message.")
    await remove_auth_channel(chat_id)
    await message.reply_text(f"✅ Un-Authorized channel: `{chat_id}`", parse_mode=ParseMode.MARKDOWN)

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

pending_changes: Dict[int, Tuple[int, int]] = {}

@app.on_message(filters.command(["changebutton", "cb"]))
async def change_button_start(client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.forward_origin:
        return await message.reply_text("❌ Reply to a forwarded channel post to change its buttons.")
    channel_id = message.reply_to_message.forward_origin.chat.id
    msg_id = message.reply_to_message.forward_origin.message_id
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
    if not message.reply_to_message or not message.reply_to_message.forward_origin:
        return await message.reply_text("❌ Please reply to the same forwarded post with the new buttons.")
    channel_id, msg_id = pending_changes.get(uid)
    orig_chat = message.reply_to_message.forward_origin.chat.id
    orig_msg_id = message.reply_to_message.forward_origin.message_id
    if orig_chat != channel_id or orig_msg_id != msg_id:
        pending_changes.pop(uid, None)
        return await message.reply_text("❌ Reply must be to the same forwarded post you used with /cb. Start again with /cb.")
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

@app.on_message(filters.channel)
async def remove_forward_tag_handler(client, message: Message):
    if not message.forward_origin:
        return
    channel_id = message.chat.id
    if not await is_channel_authed(channel_id):
        return
    try:
        await client.copy_message(
            chat_id=channel_id,
            from_chat_id=message.chat.id,
            message_id=message.id,
            reply_markup=message.reply_markup,
            caption=message.caption if getattr(message, "caption", None) else None
        )
        await message.delete()
    except Exception as e:
        print(f"[remove_forward_tag_handler] failed for chat {channel_id} msg {message.id}: {e}")
