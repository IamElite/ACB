from pyrogram import Client, filters
from DURGESH import app
from config import ADMINS


@app.on_message(
    filters.command(["eco", "e"], prefixes=["/", "!", ".", ""])
    & filters.reply
    & filters.user(ADMINS)
)
async def eco_reply(_, m):
    if not (r := m.reply_to_message):
        return await m.reply("Reply to a message.")
    if len(parts := m.text.split(maxsplit=1)) < 2:
        return await m.reply("Give text to echo.")
    await m.delete()
    await r.reply(parts[1])
