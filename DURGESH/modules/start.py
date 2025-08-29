from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

@app.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    await message.reply_text(
        text=f"🌟 Hello {message.from_user.mention}, I'm {client.me.mention}!\n\nI'm here to help you. Use /help to see what I can do.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛠 Help", callback_data="help")],
            [InlineKeyboardButton("➕ Add me to your group", url=f"https://t.me/{client.me.username}?startgroup=true")]
        ])
    )