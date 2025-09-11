import asyncio, re
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from DURGESH import app
from DURGESH.database import db

# DB collections
featuredb = db.button_feature  # store which channels/groups have button feature ON
buttondb = db.button_settings   # store custom buttons

DEFAULT_BUTTON = [["❖ ʙᴧᴄᴋᴜᴘ ʀєᴧʟϻ ❖", "https://t.me/SyntaxRealm"]]


# -------------------- CHANNEL COMMAND -------------------- #
@app.on_message(filters.channel & filters.text)
async def channel_ab_handler(client, message: Message):
    if not message.text:
        return

    # Regex match for /ab or /addbutton
    match = re.match(r"^/(ab|addbutton)\s+(on|off)$", message.text.strip(), re.IGNORECASE)
    if not match:
        return

    action = match.group(2).lower()
    chat_id = str(message.chat.id)  # always string for DB

    if action == "on":
        await featuredb.update_one({"chat_id": chat_id}, {"$set": {"chat_id": chat_id}}, upsert=True)
        msg = await message.reply_text("✅ Button feature ENABLED for this channel.")
    else:
        await featuredb.delete_one({"chat_id": chat_id})
        msg = await message.reply_text("✅ Button feature DISABLED for this channel.")

    # Clean chat
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


from pyrogram.enums import ParseMode

# -------------------- BULK ADD BUTTON -------------------- #
@app.on_message(filters.command(["setallbutton", "sab"]))
async def set_all_button(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage:\n/sab <channel_id>\n/sab <msg_link1> <msg_link2> ...")

    args = message.command[1:]
    button_data = await buttondb.find_one({"global": True})
    button = button_data.get("button", DEFAULT_BUTTON[0]) if button_data else DEFAULT_BUTTON[0]
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(button[0], url=button[1])]])

    # Mode 1: channel_id given
    if len(args) == 1 and args[0].isdigit():
        channel_id = int(args[0])
        count = 0
        async for msg in client.get_chat_history(channel_id, limit=2000):  # limit adjust karna
            if msg.video and not msg.reply_markup:
                try:
                    await client.edit_message_reply_markup(channel_id, msg.id, reply_markup=keyboard)
                    count += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print("Skip:", e)
        return await message.reply_text(f"✅ Added button to {count} video posts in {channel_id}")

    # Mode 2: specific links
    else:
        count = 0
        for link in args:
            try:
                match = re.match(r"https://t\.me/c/(-?\d+)/(\d+)", link)
                if not match:
                    continue
                channel_id = int("-100" + match.group(1))
                msg_id = int(match.group(2))
                msg = await client.get_messages(channel_id, msg_id)
                if msg.video:
                    await client.edit_message_reply_markup(channel_id, msg_id, reply_markup=keyboard)
                    count += 1
            except Exception as e:
                print("Skip:", e)
        return await message.reply_text(f"✅ Added button to {count} selected messages")

# -------------------- BULK REMOVE BUTTON -------------------- #
@app.on_message(filters.command(["rmallbutton", "rmab"]))
async def remove_all_button(client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Usage:\n/rmab <channel_id>\n/rmab <msg_link1> <msg_link2> ...")

    args = message.command[1:]
    removed = 0

    # Mode 1: channel_id given
    if len(args) == 1 and args[0].isdigit():
        channel_id = int(args[0])
        async for msg in client.get_chat_history(channel_id, limit=2000):
            if msg.video and msg.reply_markup:
                try:
                    await client.edit_message_reply_markup(channel_id, msg.id, reply_markup=None)
                    removed += 1
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print("Skip:", e)
        return await message.reply_text(f"✅ Removed buttons from {removed} video posts in {channel_id}")

    # Mode 2: specific links
    else:
        for link in args:
            try:
                match = re.match(r"https://t\.me/c/(-?\d+)/(\d+)", link)
                if not match:
                    continue
                channel_id = int("-100" + match.group(1))
                msg_id = int(match.group(2))
                msg = await client.get_messages(channel_id, msg_id)
                if msg.video and msg.reply_markup:
                    await client.edit_message_reply_markup(channel_id, msg_id, reply_markup=None)
                    removed += 1
            except Exception as e:
                print("Skip:", e)
        return await message.reply_text(f"✅ Removed buttons from {removed} selected messages")


# -------------------- VIDEO MESSAGE HANDLER -------------------- #
@app.on_message(filters.video & (filters.group | filters.channel))
async def attach_button_to_video(client, message: Message):
    chat_id = str(message.chat.id)   # 🔥 always string

    # Check DB
    feature = await featuredb.find_one({"chat_id": chat_id})
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
