import asyncio
import random

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatType

from config import STICKER, FSUB, IMG
from ChatBot import app
from ChatBot.database import add_user, add_chat, get_fsub

# **Logger Group ID (Set your log group ID here)**
LOGGER_ID = -100XXXXXXXXXX  # Replace with your actual log group ID


@app.on_message(filters.command(["start", "aistart"]) & ~filters.bot)
async def start(client, m: Message):
    if FSUB and not await get_fsub(client, m):
        return

    bot_name = app.name

    if m.chat.type == ChatType.PRIVATE:
        user_id = m.from_user.id
        await add_user(user_id, m.from_user.username or None)

        if STICKER and isinstance(STICKER, list):
            sticker_to_send = random.choice(STICKER)
            umm = await m.reply_sticker(sticker=sticker_to_send)
            await asyncio.sleep(2)
            await umm.delete()

        # **Send log message to the logging group**
        await log_start(m)

        await m.reply_photo(
            photo=random.choice(IMG),
            caption=f"""
<b>Hey {m.from_user.mention}. 💖</b>  

Welcome to <b>{bot_name}</b>. ✨  
I'm here to chat, vibe, and bring some fun to your day.  

💌 Add me to your group for even more excitement.  
""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(text="ᴀᴅᴅ ᴍᴇ ʙᴀʙʏ", url=f"https://t.me/{app.username}?startgroup=true")],
                [
                    InlineKeyboardButton(text="ᴄʜᴀɴɴᴇʟ", url="https://t.me/C0DE_SEARCH"),
                    InlineKeyboardButton(text="sᴜᴘᴘᴏʀᴛ", url="https://t.me/AsuraaSupports")
                ],
                [InlineKeyboardButton(text="ᴍʏ ᴄᴏᴍᴍᴀɴᴅs", callback_data="help")]
            ])
        )
    elif m.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
        chat_id = m.chat.id
        await add_chat(chat_id, m.chat.title)
        await m.reply_text(f"Hey {m.from_user.mention}, I’m {bot_name}, here to keep the energy high. Use /help to see what I can do!")


async def log_start(message: Message):
    text = f"""
❖ {message.from_user.mention} ᴊᴜsᴛ sᴛᴀʀᴛᴇᴅ ᴛʜᴇ ʙᴏᴛ.
    
<b>● ᴜsᴇʀ ɪᴅ ➥</b> <code>{message.from_user.id}</code>
<b>● ᴜsᴇʀɴᴀᴍᴇ ➥</b> @{message.from_user.username if message.from_user.username else 'No Username'}
    """
    
    try:
        await app.send_message(LOGGER_ID, text)
    except Exception as e:
        print(f"Logging Error: {e}")


@app.on_message(filters.command("help") & filters.group)
async def help(client, m: Message):
    await m.reply(
        "Need help? Click below to see all my commands.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 ᴄᴏᴍᴍᴀɴᴅs ᴀɴᴅ ɢᴜɪᴅᴇ", url="http://t.me/MissAaru_Robot?start=help")]
        ])
    )


@app.on_callback_query()
async def callback(client, query: CallbackQuery):
    bot_name = app.name

    if query.data == "start":
        if query.message.chat.type == ChatType.PRIVATE:
            new_text = f"""
<b>Hey {query.from_user.mention}. 💖</b>  

Welcome to <b>{bot_name}</b>. ✨  
I'm here to chat, vibe, and bring some fun to your day.  

💌 Add me to your group for even more excitement.  
"""

            if query.message.text != new_text:
                await query.message.edit_text(
                    new_text,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(text="ᴀᴅᴅ ᴍᴇ ʙᴀʙʏ", url="https://t.me/MissAaru_Robot?startgroup=true")],
                        [
                            InlineKeyboardButton(text="ᴄʜᴀɴɴᴇʟ", url="https://t.me/C0DE_SEARCH"),
                            InlineKeyboardButton(text="sᴜᴘᴘᴏʀᴛ", url="https://t.me/AsuraaSupports")
                        ],
                        [InlineKeyboardButton(text="ᴍʏ ᴄᴏᴍᴍᴀɴᴅs", callback_data="help")]
                    ])
                )

    elif query.data == "help":
        if query.message.chat.type == ChatType.PRIVATE:
            help_message = f"""
❖ Available Commands.

⬤ /start ➥ Start me.  
⬤ /ping ➥ Check if I'm online.  
⬤ /stats ➥ Get chat stats.  
⬤ /chatbot ➥ Toggle AI replies (only works in groups).  
⬤ /kiss ➥ Get a virtual kiss from me. 😘  
⬤ /hug ➥ Let me wrap you in a warm hug. 🤗 
⬤ /waifu ➥ Want a cute waifu image? Just drop a tag, and I'll fetch one for you. 💕

Stay sharp, stay awesome. ✨  
"""

            if query.message.text != help_message:
                await query.message.edit_text(
                    help_message,
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(text="ʙᴀᴄᴋ", callback_data="start"),
                            InlineKeyboardButton(text="ᴄʜᴀɴɴᴇʟ", url="https://t.me/C0DE_SEARCH")
                        ]
                    ])
                )