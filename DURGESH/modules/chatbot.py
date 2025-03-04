import asyncio
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatAction

from DURGESH import app
from DURGESH.database import is_chatbot_enabled, enable_chatbot, disable_chatbot, durga_api, is_admins


async def text_filter(_, __, m: Message):
    """Filters valid chatbot messages."""
    return (
        bool(m.text)
        and len(m.text) <= 69
        and not m.text.startswith(("!", "/"))
        and (not m.reply_to_message or m.reply_to_message.reply_to_message_id == m._client.me.id)
    )

chatbot_filter = filters.create(text_filter)


@app.on_message(
    ((filters.text & filters.group & chatbot_filter) | filters.mentioned) 
    & ~filters.bot 
    & ~filters.sticker
)
async def chatbot(_, message: Message):
    """Replies with chatbot response if enabled or when mentioned."""
    chat_id = message.chat.id

    if not await is_chatbot_enabled(chat_id) and not message.mentioned:
        return

    await app.send_chat_action(chat_id, ChatAction.TYPING)
    reply = durga_api.ask_question(message.text)
    await message.reply_text(reply or "❖ ChatBot Error. Contact @net_pro_max.")


@app.on_message(filters.command(["chatbot"]) & filters.group & ~filters.bot)
@is_admins
async def chatbot_toggle(_, message: Message):
    """Shows chatbot enable/disable options."""
    await message.reply_text(
        "❖ Choose an option to enable/disable chatbot.",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("ᴇɴᴀʙʟᴇ", callback_data="addchat"),
                InlineKeyboardButton("ᴅɪsᴀʙʟᴇ", callback_data="rmchat"),
            ]
        ]),
    )


@app.on_callback_query(filters.regex("addchat|rmchat") & ~filters.bot)
@is_admins
async def chatbot_callback(_, query: CallbackQuery):
    """Handles enabling/disabling chatbot."""
    chat_id = query.message.chat.id

    if query.data == "addchat":
        if await is_chatbot_enabled(chat_id):
            await query.edit_message_text(f"❖ Chatbot enabled by {query.from_user.mention}.")  
            return
        await enable_chatbot(chat_id)
        await query.edit_message_text(f"❖ Chatbot enabled by {query.from_user.mention}.")

    elif query.data == "rmchat":
        if not await is_chatbot_enabled(chat_id):
            await query.edit_message_text(f"❖ Chatbot disabled by {query.from_user.mention}.")
            return
        await disable_chatbot(chat_id)
        await query.edit_message_text(f"❖ Chatbot disabled by {query.from_user.mention}.")
