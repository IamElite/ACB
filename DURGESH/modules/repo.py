from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from DURGESH import app

@app.on_message(filters.command("repo"))
async def start(_, msg):
    await msg.reply_photo(
        photo="https://i.postimg.cc/FF2Jv8D0/ec107964b90c959da231293998b6d73e.jpg",
        caption="""Hey there, I'm Durgesh, your AI chatbot. ♥︎

If you want my bot repo, click below to get the source code.

Powered by @net_pro_max ✨""",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("sᴜᴘᴘᴏʀᴛ", url="https://t.me/net_pro_max"),
             InlineKeyboardButton("ʀᴇᴘᴏ", url="https://t.me/+cXIPgHSuJnxiNjU1")]
        ])
    )