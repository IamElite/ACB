import os
import requests
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ParseMode,
)
from DURGESH import app
from config import ADMINS      # adjust the import path to your project

@app.on_message(
    filters.command(["tgm", "tgt", "telegraph", "tl"])
    & filters.user(ADMINS)
)
async def get_link_group(client, message):
    if not message.reply_to_message:
        return await message.reply("Pʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇᴅɪᴀ ᴛᴏ ᴜᴘʟᴏᴀᴅ.")

    media = message.reply_to_message
    file_size = getattr(media, media.media.value).file_size if media.media else 0
    if file_size > 200 * 1024 * 1024:
        return await message.reply("Fɪʟᴇ sɪᴢᴇ sʜᴏᴜʟᴅ ʙᴇ ᴜɴᴅᴇʀ 200MB.")

    temp_msg = await message.reply("Pʀᴏᴄᴇssɪɴɢ...")

    async def progress(current, total):
        try:
            await temp_msg.edit_text(f"📥 Dᴏᴡɴʟᴏᴀᴅɪɴɢ... {current * 100 / total:.1f}%")
        except Exception:
            pass

    try:
        file_path = await media.download(progress=progress)
        await temp_msg.edit_text("📤 Uᴘʟᴏᴀᴅɪɴɢ...")

        with open(file_path, "rb") as f:
            r = requests.post(
                "https://catbox.moe/user/api.php",
                data={"reqtype": "fileupload", "json": "true"},
                files={"fileToUpload": f},
            )

        if r.status_code == 200:
            link = r.text.strip()
            await temp_msg.edit_text(
                f"🌐 | [👉 Yᴏᴜʀ Lɪɴᴋ 👈]({link})",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("Cʀᴇᴀᴛᴇᴅ ʙʏ Dᴜʀɢᴇsʜ", url=link)]]
                ),
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            await temp_msg.edit_text(
                f"❌ Uᴘʟᴏᴀᴅ Fᴀɪʟᴇᴅ\n\n<i>Rᴇᴀsᴏɴ: {r.status_code} - {r.text}</i>"
            )
    except Exception as e:
        await temp_msg.edit_text(f"❌ Fɪʟᴇ ᴜᴘʟᴏᴀᴅ ғᴀɪʟᴇᴅ\n\n<i>Rᴇᴀsᴏɴ: {e}</i>")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
