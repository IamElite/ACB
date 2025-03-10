import asyncio
import random

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from pyrogram.enums import ChatType

from config import STICKER, FSUB, IMG, OWNER_ID
from DURGESH import app
from DURGESH.database import add_user, add_chat, get_fsub

# OWNER_ID ke DM mein log bhejne ke liye function
async def log_start(message: Message):
    text = f"""
❖ {message.from_user.mention} just started the bot.
    
<b>● User ID ➥</b> <code>{message.from_user.id}</code>
<b>● Username ➥</b> @{message.from_user.username if message.from_user.username else 'No Username'}
    """
    try:
        # OWNER_ID ke DM mein message send hoga
        await app.send_message(OWNER_ID, text)
    except Exception as e:
        print(f"Logging Error: {e}")


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

        # OWNER_ID ke DM mein log message bhejne ke liye call
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
                    InlineKeyboardButton(text="ᴄʜᴀɴɴᴇʟ", url="https://t.me/net_pro_max"),
                    InlineKeyboardButton(text="sᴜᴘᴘᴏʀᴛ", url="https://t.me/+cXIPgHSuJnxiNjU1")
                ],
                [InlineKeyboardButton(text="ᴍʏ ᴄᴏᴍᴍᴀɴᴅs", callback_data="help")]
            ])
        )
    elif m.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}:
        chat_id = m.chat.id
        await add_chat(chat_id, m.chat.title)
        await m.reply_text(f"Hey {m.from_user.mention}, I’m {bot_name}, here to keep the energy high. Use /help to see what I can do!")


@app.on_message(filters.command("help") & filters.group)
async def help(client, m: Message):
    await m.reply(
        "Need help? Click below to see all my commands.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📜 ᴄᴏᴍᴍᴀɴᴅs ᴀɴᴅ ɢᴜɪᴅᴇ", url="http://t.me/Era_Roxbot?start=help")]
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
                        [InlineKeyboardButton(text="ᴀᴅᴅ ᴍᴇ ʙᴀʙʏ", url="https://t.me/Era_Roxbot?startgroup=true")],
                        [
                            InlineKeyboardButton(text="ᴄʜᴀɴɴᴇʟ", url="https://t.me/net_pro_max"),
                            InlineKeyboardButton(text="sᴜᴘᴘᴏʀᴛ", url="https://t.me/+cXIPgHSuJnxiNjU1")
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

Stay sharp, stay awesome. ✨  
"""
            if query.message.text != help_message:
                await query.message.edit_text(
                    help_message,
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton(text="ʙᴀᴄᴋ", callback_data="start"),
                            InlineKeyboardButton(text="ᴄʜᴀɴɴᴇʟ", url="https://t.me/net_pro_max")
                        ]
                    ])
                )



async def set_default_status(chat_id):
    try:
        if not await status_db.find_one({"chat_id": chat_id}):
            await status_db.insert_one({"chat_id": chat_id, "status": "enabled"})
    except Exception as e:
        print(f"Error setting default status for chat {chat_id}: {e}")

@app.on_message(filters.new_chat_members)
async def welcome_in_new_chat(client, message: Message):
    chat_id = message.chat.id
    await add_chat(chat_id, message.chat.title)
    await set_default_status(chat_id)
    chats = len(await get_chats())
    try:
        for member in message.new_chat_members:
            if member.id == app.id:
                reply_markup = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("sᴇʟᴇᴄᴛ ʟᴀɴɢᴜᴀɢᴇ", callback_data="choose_lang")]]
                )
                await message.reply_photo(
                    photo=random.choice(IMG),
                    caption=START.format(app.mention or "can't mention", chats),
                    reply_markup=reply_markup
                )
                chat = message.chat
                try:
                    invitelink = await app.export_chat_invite_link(chat_id)
                    link = f"[ɢᴇᴛ ʟɪɴᴋ]({invitelink})"
                except ChatAdminRequired:
                    link = "No Link"
                try:
                    groups_photo = await app.download_media(
                        chat.photo.big_file_id, file_name=f"chatpp{chat_id}.png"
                    )
                    chat_photo = groups_photo if groups_photo else "https://envs.sh/_2L.png"
                except Exception:
                    chat_photo = "https://envs.sh/_2L.png"
                count = await app.get_chat_members_count(chat_id)
                username = chat.username if chat.username else "𝐏ʀɪᴠᴀᴛᴇ 𝐆ʀᴏᴜᴘ"
                msg = (
                    f"**📝 𝐌ᴜsɪᴄ 𝐁ᴏᴛ 𝐀ᴅᴅᴇᴅ 𝐈ɴ 𝐀 #𝐍ᴇᴡ_𝐆ʀᴏᴜᴘ**\n\n"
                    f"**📌 𝐂ʜᴀᴛ 𝐍ᴀᴍᴇ:** {chat.title}\n"
                    f"**🍂 𝐂ʜᴀᴛ 𝐈ᴅ:** `{chat_id}`\n"
                    f"**🔐 𝐂ʜᴀᴛ 𝐔sᴇʀɴᴀᴍᴇ:** @{username}\n"
                    f"**🖇️ 𝐆ʀᴏᴜᴘ 𝐋ɪɴᴋ:** {link}\n"
                    f"**📈 𝐆ʀᴏᴜᴘ 𝐌ᴇᴍʙᴇʀs:** {count}\n"
                    f"**🤔 𝐀ᴅᴅᴇᴅ 𝐁ʏ:** {message.from_user.mention}\n\n"
                    f"**ᴛᴏᴛᴀʟ ᴄʜᴀᴛs:** {chats}"
                )
                try:
                    await app.send_photo(
                        int(OWNER_ID),
                        photo=chat_photo,
                        caption=msg,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(f"{message.from_user.first_name}", user_id=message.from_user.id)]
                        ])
                    )
                except Exception as e:
                    logging.info(f"Error sending photo to owner: {e}")
                break
    except Exception as e:
        logging.info(f"Error in welcome_in_new_chat: {e}")
