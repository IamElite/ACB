import asyncio, random, re, requests
from pyrogram import Client, filters
from DURGESH import app
from DURGESH.database import CAPTIONS

# Hug trigger: agar message text mein "hug" shabd (case-insensitive) aaye
@app.on_message(filters.text & filters.regex(r"\b(hug)\b", flags=re.IGNORECASE))
async def auto_hug(client, message):
    api_url = "https://myown.codesearch.workers.dev/hug"
    try:
        # Blocking HTTP request ko asynchronous tarike se run karne ke liye asyncio.to_thread use kar rahe hain
        response = await asyncio.to_thread(lambda: __import__("requests").get(api_url).json())
        hug_url = response.get("data")
        if hug_url:
            reply_id = message.reply_to_message.id if message.reply_to_message else message.id
            # CAPTIONS list se random caption choose karein
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


# Kiss trigger: agar message text mein "kiss" shabd (case-insensitive) aaye
@app.on_message(filters.text & filters.regex(r"\b(kiss)\b", flags=re.IGNORECASE))
async def auto_kiss(client, message):
    api_url = "https://myown.codesearch.workers.dev/kiss"
    try:
        response = await asyncio.to_thread(lambda: __import__("requests").get(api_url).json())
        kiss_url = response.get("data")
        if kiss_url:
            reply_id = message.reply_to_message.id if message.reply_to_message else message.id
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


# Available tags for waifu API
WAIFU_TAGS = [
    "maid", "waifu", "marin-kitagawa", "mori-calliope",
    "raiden-shogun", "oppai", "selfies", "uniform", "kamisato-ayaka",
    "ass", "hentai", "milf", "oral", "paizuri", "ecchi", "ero"
]

# Function to fetch waifu image
def get_waifu(tag):
    api_url = f"https://waifu.codesearch.workers.dev/?tag={tag}"
    try:
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json().get("image_url")
    except requests.exceptions.RequestException:
        return None
    return None
 
#@app.on_message((filters.command("waifu")  #for /waifu command 
@app.on_message(filters.text & filters.regex(r"\bwaifu\b", flags=re.IGNORECASE)) # Waifu trigger: message text mein "waifu" word detect hone par trigger ho
async def auto_waifu(client, message):
    selected_tag = random.choice(WAIFU_TAGS)
    image_url = await asyncio.to_thread(get_waifu, selected_tag)
    if image_url:
        reply_id = message.reply_to_message.id if message.reply_to_message else message.id
        caption = f"**Cᴀᴛᴇɢᴏʀʏ:** {selected_tag.capitalize()}\n\n{random.choice(CAPTIONS)}"
        await client.send_photo(
            chat_id=message.chat.id,
            photo=image_url,
            caption=caption,
            reply_to_message_id=reply_id
        )
    else:
        await message.reply_text("Exɪsᴛᴇɴᴄᴇ ɪs ᴀ ᴘʜᴀɴᴛᴀsᴍ :)")
