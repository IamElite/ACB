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
            chat_id = int(message.command[1])
        except ValueError:
            return await message.reply_text("❌ Invalid channel_id!")
    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        # FIX: Use forward_from_chat instead of forward_origin
        chat_id = message.reply_to_message.forward_from_chat.id
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
    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        # FIX: Use forward_from_chat instead of forward_origin
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
        # Improved regex for better parsing
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
    match = re.match(r"https://t\.me/c/(-?\d+)/(\d+)", link)
    if not match:
        return await message.reply_text("❌ Invalid link format! Use: https://t.me/c/<channel_id>/<msg_id>")

    channel_id, msg_id = int("-100" + match.group(1)), int(match.group(2))

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

async def safe_copy_and_delete(msg: Message, chat_id: int):
    try:
        if msg.text:
            await msg.copy(
                chat_id,
                entities=msg.entities,
                reply_markup=msg.reply_markup
            )
        else:
            await msg.copy(
                chat_id,
                caption=msg.caption,
                caption_entities=msg.caption_entities,
                reply_markup=msg.reply_markup
            )
        await msg.delete()
    except Exception as e:
        if "FLOOD_WAIT" in str(e):
            wait = int(str(e).split("wait ")[1].split()[0])
            await asyncio.sleep(wait)
            try:
                if msg.text:
                    await msg.copy(
                        chat_id,
                        entities=msg.entities,
                        reply_markup=msg.reply_markup
                    )
                else:
                    await msg.copy(
                        chat_id,
                        caption=msg.caption,
                        caption_entities=msg.caption_entities,
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
    if not (message.forward_from_chat or message.via_bot):
        return
    if not await is_channel_authed(message.chat.id):
        return
    # FIX: Removed extra 'cap' parameter
    await safe_copy_and_delete(message, message.chat.id)
