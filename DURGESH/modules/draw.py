import io
import urllib.parse
import aiohttp
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from DURGESH import app
from config import IMG_GEN_API  # IMG_GEN_API ko config module se import karo

# Global dictionary to store session data for each user
draw_sessions = {}

# List of available models with short description (3-6 words)
MODELS = [
    ("flux", "Classic look"),
    ("flux-realism", "Realistic style"),
    ("flux-4o", "Creative vibe"),
    ("flux-pixel", "Pixel art"),
    ("flux-anime", "Anime style"),
    ("flux-3d", "3D appearance"),
]

# List of available sizes
SIZES = ["1:1", "16:9", "9:16", "21:9", "9:21", "1:2", "2:1"]

# /draw and /fastdraw command handler
@app.on_message(filters.command(["draw", "fastdraw"]))
async def draw_command(client, message):
    if len(message.command) < 2:
        await message.reply("Usage: /draw <prompt> or /fastdraw <prompt>")
        return
    prompt = " ".join(message.command[1:])
    # Determine endpoint based on command: /draw -> v1/imagine, /fastdraw -> v1/imagine2
    cmd = message.command[0]
    endpoint = "v1/imagine" if cmd == "draw" else "v1/imagine2"
    # Store session data using user's ID
    user_id = message.from_user.id
    draw_sessions[user_id] = {
        "prompt": prompt,
        "endpoint": endpoint
    }
    # Prepare inline keyboard for model selection
    buttons = []
    for model, desc in MODELS:
        buttons.append(InlineKeyboardButton(f"{model}\n{desc}", callback_data=f"model:{model}"))
    keyboard = InlineKeyboardMarkup([buttons[i:i+2] for i in range(0, len(buttons), 2)])
    await message.reply("Select a model:", reply_markup=keyboard)

# Callback handler for model selection
@app.on_callback_query(filters.regex(r"^model:"))
async def model_callback(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in draw_sessions:
        await callback_query.answer("Session expired. Please send the command again.", show_alert=True)
        return
    model = callback_query.data.split(":", 1)[1]
    draw_sessions[user_id]["model"] = model
    # Prepare inline keyboard for size selection
    buttons = []
    for size in SIZES:
        buttons.append(InlineKeyboardButton(size, callback_data=f"size:{size}"))
    keyboard = InlineKeyboardMarkup([buttons[i:i+3] for i in range(0, len(buttons), 3)])
    await callback_query.message.edit_text("Select a size:", reply_markup=keyboard)
    await callback_query.answer()

# Callback handler for size selection
@app.on_callback_query(filters.regex(r"^size:"))
async def size_callback(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in draw_sessions:
        await callback_query.answer("Session expired. Please send the command again.", show_alert=True)
        return
    size = callback_query.data.split(":", 1)[1]
    draw_sessions[user_id]["size"] = size
    session_data = draw_sessions.pop(user_id)  # Remove session after processing
    prompt = session_data["prompt"]
    model = session_data["model"]
    endpoint = session_data["endpoint"]
    base_url = f"{IMG_GEN_API}/{endpoint}"
    params = {
        "prompt": prompt,
        "size": size,
        "model": model
    }
    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                image_bytes = await resp.read()
                caption = f"Prompt: {prompt}\nSize: {size}\nModel: {model}"
                await callback_query.message.reply_photo(photo=image_bytes, caption=caption)
                await callback_query.answer("Image generated!")
            else:
                await callback_query.answer(f"Error: API returned status {resp.status}", show_alert=True)
