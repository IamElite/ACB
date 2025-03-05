from DURGESH import app
import random
import logging
from config import OWNER_ID, IMG
from DURGESH.database import add_user, add_chat, get_chats
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import ChatAdminRequired

async def get_bot_id():
    me = await app.get_me()
    return me.id, me.mention or "Bot"

@app.on_message(filters.new_chat_members)
async def welcome_jej(client, message: Message):
    try:
        await add_chat(message.chat.id)
        if message.from_user:
            await add_user(message.from_user.id)
        chats = len(await get_chats())
        users = "N/A"
        bot_id, bot_mention = await get_bot_id()
        for member in message.new_chat_members:
            if member.id == bot_id:
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("sᴇʟᴇᴄᴛ ʟᴀɴɢᴜᴀɢᴇ", callback_data="choose_lang")]
                ])
                await message.reply_photo(
                    photo=random.choice(IMG),
                    caption=(
                        "Welcome {0}!\n"
                        "Total Users: {1}\n"
                        "Total Chats: {2}\n\n"
                        "Select your language using the button below."
                    ).format(bot_mention, users, chats),
                    reply_markup=reply_markup
                )
                chat = message.chat
                try:
                    invitelink = await app.export_chat_invite_link(chat.id)
                    link = f"[ɢᴇᴛ ʟɪɴᴋ]({invitelink})"
                except ChatAdminRequired:
                    link = "No Link"
                try:
                    if chat.photo:
                        groups_photo = await app.download_media(
                            chat.photo.big_file_id, file_name=f"chatpp{chat.id}.png"
                        )
                        chat_photo = groups_photo if groups_photo else "https://envs.sh/_2L.png"
                    else:
                        chat_photo = "https://envs.sh/_2L.png"
                except Exception as e:
                    logging.exception("Error downloading chat photo:")
                    chat_photo = "https://envs.sh/_2L.png"
                count = await app.get_chat_members_count(chat.id)
                username = chat.username if chat.username else "𝐏ʀɪᴠᴀᴛᴇ 𝐆ʀᴏᴜᴘ"
                msg = (
                    f"**📝𝐌ᴜsɪᴄ 𝐁ᴏᴛ 𝐀ᴅᴅᴇᴅ 𝐈ɴ 𝐀 #𝐍ᴇᴡ_𝐆ʀᴏᴜᴘ**\n\n"
                    f"**📌𝐂ʜᴀᴛ 𝐍ᴀᴍᴇ:** {chat.title}\n"
                    f"**🍂𝐂ʜᴀᴛ 𝐈ᴅ:** `{chat.id}`\n"
                    f"**🔐𝐂ʜᴀᴛ 𝐔sᴇʀɴᴀᴍᴇ:** @{username}\n"
                    f"**🖇️𝐆ʀᴏᴜᴘ 𝐋ɪɴᴋ:** {link}\n"
                    f"**📈𝐆ʀᴏᴜᴘ 𝐌ᴇᴍʙᴇʀs:** {count}\n"
                    f"**🤔𝐀ᴅᴅᴇᴅ 𝐁ʏ:** {message.from_user.mention if message.from_user else 'Unknown'}\n\n"
                    f"**ᴛᴏᴛᴀʟ ᴄʜᴀᴛs :** {chats}"
                )
                try:
                    await app.send_photo(
                        int(OWNER_ID),
                        photo=chat_photo,
                        caption=msg,
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton(message.from_user.first_name if message.from_user else "User", user_id=message.from_user.id if message.from_user else 0)]
                        ])
                    )
                except Exception as e:
                    logging.exception("Error sending photo to owner:")
    except Exception as e:
        logging.exception("Error in welcome handler:")
