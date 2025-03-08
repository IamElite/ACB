from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from DURGESH import app 

# Har chat ke liye forward deletion mode store karne ke liye global dictionary
forward_mode = {}

# /forward command handler (group chats ke liye)
@app.on_message(filters.command("forward") & filters.group)
def forward_command(client, message):
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("On", callback_data="fw_on"),
            InlineKeyboardButton("Off", callback_data="fw_off")
        ]]
    )
    message.reply_text("Forward deletion mode set karo:", reply_markup=keyboard)

# Callback query handler (inline button presses ke liye)
@app.on_callback_query()
def button_handler(client, callback_query):
    chat_id = callback_query.message.chat.id
    data = callback_query.data

    if data == "fw_on":
        forward_mode[chat_id] = True
        callback_query.answer("Forward deletion enabled!")
    elif data == "fw_off":
        forward_mode[chat_id] = False
        callback_query.answer("Forward deletion disabled!")
    
    new_text = f"Forward deletion mode is now {'ON' if forward_mode.get(chat_id) else 'OFF'}."
    callback_query.edit_message_text(new_text)

# Group messages ke liye auto-delete handler
@app.on_message(filters.group)
def auto_delete_forwarded(client, message):
    chat_id = message.chat.id
    # Agar mode ON hai aur message forwarded hai
    if forward_mode.get(chat_id, False) and message.forward_date:
        try:
            message.delete()
        except Exception as e:
            print(f"Error deleting message: {e}")
