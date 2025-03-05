import asyncio, random, re
from pyrogram import Client, filters
from DURGESH import app
from DURGESH.database import CAPTIONS

# Message filter: agar message text mein "hug" shabd ho (case-insensitive)
@app.on_message(filters.regex(r"\b(hug)\b", flags=re.IGNORECASE))
async def auto_hug(client, message):
    api_url = "https://myown.codesearch.workers.dev/hug"
    try:
        response = await asyncio.to_thread(lambda: requests.get(api_url).json())
        hug_url = response.get("data")
        if hug_url:
            reply_id = message.reply_to_message.id if message.reply_to_message else message.id
            # CAPTIONS list se random caption select
            caption = random.choice(CAPTIONS)
            await client.send_animation(
                chat_id=message.chat.id,
                animation=hug_url,
                caption=caption,
                reply_to_message_id=reply_id
            )
        else:
            await message.reply_text("Aʟʟ ɪs ᴀ ғɪɢᴍᴇɴᴛ ᴏғ ɪᴍᴀɢɪɴᴀᴛɪᴏɴ :)")
    except Exception as e:
        await message.reply_text("Lɪғᴇ ɪs ᴀ ɢʀᴀɴᴅ ᴅᴇᴄᴇᴘᴛɪᴏɴ :)")

# Message filter: agar message text mein "kiss" shabd ho (case-insensitive)
@app.on_message(filters.regex(r"\b(kiss)\b", flags=re.IGNORECASE))
async def auto_kiss(client, message):
    api_url = "https://myown.codesearch.workers.dev/kiss"
    try:
        response = await asyncio.to_thread(lambda: requests.get(api_url).json())
        kiss_url = response.get("data")
        if kiss_url:
            reply_id = message.reply_to_message.id if message.reply_to_message else message.id
            # Random caption select using CAPTIONS list
            caption = random.choice(CAPTIONS)
            await client.send_animation(
                chat_id=message.chat.id,
                animation=kiss_url,
                caption=caption,
                reply_to_message_id=reply_id
            )
        else:
            await message.reply_text("Tʜᴇ ᴜɴɪᴠᴇʀsᴇ ɪs ᴀ ᴄʜɪᴍᴇʀᴀ :)")
    except Exception as e:
        await message.reply_text("Exɪsᴛᴇɴᴄᴇ ɪs ᴀ ᴘʜᴀɴᴛᴀsᴍ :)")
