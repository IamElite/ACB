import requests
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from DURGESH import app


def get_pypi_info(package_name: str):
    try:
        api_url = f"https://pypi.org/pypi/{package_name}/json"
        response = requests.get(api_url)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Eʀʀᴏʀ ғᴇᴛᴄʜɪɴɢ PʏPI ɪɴғᴏʀᴍᴀᴛɪᴏɴ: {e}")
    return None


@app.on_message(filters.command("pypi", prefixes="/"))
async def pypi_info_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("ᴘʟᴇᴀsᴇ ᴘʀᴏᴠɪᴅᴇ ᴀ ᴘᴀᴋᴀɢᴇ ɴᴀᴍᴇ ᴀꜰᴛᴇʀ ᴛʜᴇ /pypi ᴄᴏᴍᴍᴀɴᴅ.")
        return
    package_name = message.command[1]
    pypi_info = get_pypi_info(package_name)

    if pypi_info:
        info = pypi_info.get("info", {})
        project_urls = info.get("project_urls", {})
        homepage = project_urls.get("Homepage", "ɴ/ᴀ")

        info_message = (
            f"ᴅᴇᴀʀ {message.from_user.mention}\n"
            f"ʜᴇʀᴇ ɪꜱ ʏᴏᴜʀ ᴘᴀᴋᴀɢᴇ ᴅᴇᴛᴀɪʟꜱ:\n\n"
            f"ᴘᴀᴋᴀɢᴇ ɴᴀᴍᴇ ➪ {info.get('name', 'ɴ/ᴀ')}\n"
            f"ʟᴀᴛᴇꜱᴛ ᴠᴇʀꜱɪᴏɴ ➪ {info.get('version', 'ɴ/ᴀ')}\n"
            f"ᴅᴇꜱᴄʀɪᴘᴛɪᴏɴ ➪ {info.get('summary', 'ɴ/ᴀ')}\n"
            f"ᴘʀᴏᴊᴇᴄᴛ ᴜʀʟ ➪ {homepage}"
        )
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="〆 ᴄʟᴏꜱᴇ 〆", callback_data="close")]]
        )
        await message.reply_text(info_message, reply_markup=markup)
    else:
        await message.reply_text(f"ᴘᴀᴋᴀɢᴇ '{package_name}' ɴᴏᴛ ꜰᴏᴜɴᴅ. ᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.")


@app.on_callback_query(filters.regex("^close$"))
async def close_callback(client, callback_query):
    try:
        if callback_query.message is not None:
            await callback_query.message.delete()
    except Exception as e:
        print(f"Eʀʀᴏʀ ᴅᴇʟᴇᴛɪɴɢ ᴍᴇssᴀɢᴇ: {e}")
    await callback_query.answer()
