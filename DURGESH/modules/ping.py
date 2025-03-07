import io, aiohttp
import urllib.parse
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from DURGESH import app
from config import IMG_GEN_API

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
    ("any-dark", "Dark theme")
]

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
    # Prepare inline keyboard for model selection (buttons par sirf model name)
    buttons = []
    for model, _ in MODELS:
        buttons.append(InlineKeyboardButton(model, callback_data=f"model:{model}"))
    # Arrange buttons 2 per row
    keyboard = InlineKeyboardMarkup([buttons[i:i+2] for i in range(0, len(buttons), 2)])
    # Prepare model info text (model: description)
    model_info = "\n".join([f"{model}: {desc}" for model, desc in MODELS])
    await message.reply(f"Select a model:\n\n{model_info}", reply_markup=keyboard)

# Callback handler for model selection
@app.on_callback_query(filters.regex(r"^model:"))
async def model_callback(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in draw_sessions:
        await callback_query.answer("Session expired. Please send the command again.", show_alert=True)
        return
    selected_model = callback_query.data.split(":", 1)[1]
    draw_sessions[user_id]["model"] = selected_model
    # Prepare inline keyboard for size selection arranged as required
    size_buttons = [
        [InlineKeyboardButton("9:16", callback_data="size:9:16"),
         InlineKeyboardButton("16:9", callback_data="size:16:9")],
        [InlineKeyboardButton("9:21", callback_data="size:9:21"),
         InlineKeyboardButton("21:9", callback_data="size:21:9")],
        [InlineKeyboardButton("1:2", callback_data="size:1:2"),
         InlineKeyboardButton("2:1", callback_data="size:2:1")],
        [InlineKeyboardButton("1:1", callback_data="size:1:1")]
    ]
    keyboard = InlineKeyboardMarkup(size_buttons)
    await callback_query.message.edit_text("Select a size:", reply_markup=keyboard)
    await callback_query.answer()

# Callback handler for size selection
@app.on_callback_query(filters.regex(r"^size:"))
async def size_callback(client, callback_query):
    user_id = callback_query.from_user.id
    if user_id not in draw_sessions:
        await callback_query.answer("Session expired. Please send the command again.", show_alert=True)
        return

    selected_size = callback_query.data.split(":", 1)[1]
    draw_sessions[user_id]["size"] = selected_size

    # Delete the size selection message (inline keyboard)
    try:
        await callback_query.message.delete()
    except Exception:
        pass

    # Send a waiting message to user
    waiting_msg = await callback_query.message.reply_text("Generating image, please wait...")

    session_data = draw_sessions.pop(user_id)  # Remove session after processing
    prompt = session_data["prompt"]
    model = session_data["model"]
    endpoint = session_data["endpoint"]

    base_url = f"{IMG_GEN_API}/{endpoint}"
    params = {
        "prompt": prompt,
        "size": selected_size,
        "model": model
    }
    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                image_bytes = await resp.read()
                # Convert bytes to BytesIO object with a filename
                image_stream = io.BytesIO(image_bytes)
                image_stream.name = "generated_image.jpg"
                
                caption = f"Prompt: {prompt}\nSize: {selected_size}\nModel: {model}"
                await callback_query.message.reply_photo(photo=image_stream, caption=caption)
                await waiting_msg.delete()  # Delete waiting message after sending image
                await callback_query.answer("Image generated successfully!")
            else:
                await waiting_msg.delete()  # Delete waiting message on error
                await callback_query.answer(f"Error: API returned status {resp.status}", show_alert=True)
