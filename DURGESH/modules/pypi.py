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
        print(f"Error fetching PyPI information: {e}")
    return None


@app.on_message(filters.command("pypi", prefixes="/"))
async def pypi_info_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("Please provide a package name after the /pypi command.")
        return
    package_name = message.command[1]
    pypi_info = get_pypi_info(package_name)

    if pypi_info:
        info = pypi_info.get("info", {})
        project_urls = info.get("project_urls", {})
        homepage = project_urls.get("Homepage", "N/A")

        info_message = (
            f"ᴅᴇᴀʀ {message.from_user.mention}\n"
            f"ʜᴇʀᴇ ɪs ʏᴏᴜʀ ᴘᴀᴋᴀɢᴇ ᴅᴇᴛᴀɪʟs:\n\n"
            f"ᴘᴀᴋᴀɢᴇ ɴᴀᴍᴇ ➪ {info.get('name', 'N/A')}\n"
            f"ʟᴀᴛᴇsᴛ ᴠᴇʀsɪᴏɴ ➪ {info.get('version', 'N/A')}\n"
            f"ᴅᴇsᴄʀɪᴘᴛɪᴏɴ ➪ {info.get('summary', 'N/A')}\n"
            f"ᴘʀᴏᴊᴇᴄᴛ ᴜʀʟ ➪ {homepage}"
        )
        markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="〆 ᴄʟᴏsᴇ 〆", callback_data="close")]]
        )
        await message.reply_text(info_message, reply_markup=markup)
    else:
        await message.reply_text(f"Package '{package_name}' not found. Please try again later.")


@app.on_callback_query(filters.regex("^close$"))
async def close_callback(client, callback_query):
    try:
        if callback_query.message:
            # Instead of deleting, edit the message to indicate it's closed.
            await callback_query.message.edit_text("Closed")
        await callback_query.answer("Closed")
    except Exception as e:
        print(f"Error in close_callback: {e}")
