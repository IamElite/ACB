import asyncio
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from DURGESH import app
from DURGESH.database import db

# DB collections
featuredb = db.button_feature  # store which channels/groups have button feature ON
buttondb = db.button_settings   # store custom buttons

DEFAULT_BUTTON = [["❖ ʙᴧᴄᴋᴜᴘ ʀєᴧʟϻ ❖", "https://t.me/SyntaxRealm"]]

# -------------------- ENABLE / DISABLE FEATURE -------------------- #
@app.on_message(filters.command(["addbutton", "ab"]) & (filters.group | filters.channel))
async def toggle_button_feature(client, message: Message):
    if len(message.command) != 2 or message.command[1].lower() not in ["on", "off"]:
        return await message.reply_text("❌ Usage: /addbutton on|off or /ab on|off")

    action = message.command[1].lower()
    chat_id = message.chat.id

    if action == "on":
        await featuredb.update_one({"chat_id": str(chat_id)}, {"$set": {"chat_id": str(chat_id)}}, upsert=True)
        msg = await message.reply_text("✅ Button feature ENABLED for this chat.")
    else:
        await featuredb.delete_one({"chat_id": str(chat_id)})
        msg = await message.reply_text("✅ Button feature DISABLED for this chat.")

    # Delete both bot reply and command for clean chat
    await asyncio.sleep(2)
    try:
        await msg.delete()
        await message.delete()
    except:
        pass

# -------------------- SET CUSTOM BUTTON -------------------- #
@app.on_message(filters.command(["setbutton", "sb"]))
async def set_custom_button(client, message: Message):
    if len(message.command) < 3:
        return await message.reply_text("❌ Usage: /setbutton <button_text> <url>")

    button_text = message.command[1]
    button_url = message.command[2]

    # Channel-specific if reply
    if message.reply_to_message:
        chat_id = message.reply_to_message.chat.id
        await buttondb.update_one(
            {"chat_id": str(chat_id)},
            {"$set": {"button": [button_text, button_url]}},
            upsert=True
        )
        return await message.reply_text(f"✅ Custom button set for this channel: [{button_text}]({button_url})", disable_web_page_preview=True)

    # Global button (DM)
    else:
        await buttondb.update_one(
            {"global": True},
            {"$set": {"button": [button_text, button_url]}},
            upsert=True
        )
        return await message.reply_text(f"✅ Global button set: [{button_text}]({button_url})", disable_web_page_preview=True)

# -------------------- VIDEO MESSAGE HANDLER -------------------- #
@app.on_message(filters.video & (filters.group | filters.channel))
async def attach_button_to_video(client, message: Message):
    chat_id = message.chat.id

    # Check if feature enabled
    feature = await featuredb.find_one({"chat_id": str(chat_id)})
    if not feature:
        return

    # Get button: channel-specific first, then global, then default
    btn_data = await buttondb.find_one({"chat_id": str(chat_id)})
    if btn_data:
        button = btn_data.get("button", DEFAULT_BUTTON[0])
    else:
        global_btn = await buttondb.find_one({"global": True})
        button = global_btn.get("button", DEFAULT_BUTTON[0]) if global_btn else DEFAULT_BUTTON[0]

    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(button[0], url=button[1])]])

    try:
        await message.edit_reply_markup(reply_markup=keyboard)
    except Exception as e:
        print("Failed to attach button:", e)
