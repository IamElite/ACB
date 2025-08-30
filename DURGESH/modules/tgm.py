# gen.py  (plug-in module)
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from DURGESH import app
import requests, tempfile, os

TG_TOKEN  = "d3b25feccb89e508a9114afb82aa421fe2a9712b963b387cc5ad71e58722"
CATBOX_URL = "https://catbox.moe/user/api.php"
import os
import requests
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.enums import ParseMode

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
@app.on_message(filters.command("gen"))
async def gen_post(_, msg: Message):
    if not msg.reply_to_message or not msg.reply_to_message.photo:
        return await msg.reply("❗ Kisi photo pe reply karo `/gen` se.")

    photo   = msg.reply_to_message.photo.file_id
    caption = (msg.reply_to_message.caption or "").strip()
    title   = caption[:256] or "Untitled"
    tmp_path = None

    temp_msg = await msg.reply("📤 Uploading…")

    try:
        tmp_path = await app.download_media(photo)

        with open(tmp_path, "rb") as f:
            r = requests.post(
                CATBOX_URL,
                data={"reqtype": "fileupload", "json": "true"},
                files={"fileToUpload": f},
                timeout=30
            )

        if r.status_code == 200:
            img_url = r.text.strip()
            content = [{"tag": "img", "attrs": {"src": img_url, "alt": title}}]

            tg_resp = requests.post(
                "https://api.telegra.ph/createPage",
                json={
                    "access_token": TG_TOKEN,
                    "title": title,
                    "author_name": "@SyntaxRealm ON TG",
                    "content": content
                },
                timeout=15
            ).json()

            if tg_resp.get("ok"):
                link = tg_resp["result"]["url"]
                await temp_msg.edit_text(
                    f"🌐 | [👉 Yᴏᴜʀ Lɪɴᴋ 👈]({link})",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("Cʀᴇᴀᴛᴇᴅ ʙʏ Dᴜʀɢᴇsʜ", url=link)]]
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await temp_msg.edit("❌ Telegraph error: " + str(tg_resp))
        else:
            await temp_msg.edit("❌ Catbox upload failed.")

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
