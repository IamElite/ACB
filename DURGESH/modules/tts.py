import os
import io
import urllib.parse
import aiohttp
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from DURGESH import app
from config import IMG_GEN_API

# Global dict to store TTS requests by user id
tts_requests = {}

# List of available audio models with simple names for buttons
available_audio_models = [
    {"id": "alex", "caption": "alex"},
    {"id": "sophia", "caption": "sophia"}
]

# TTS command handler: User sends /tts <text>
@app.on_message(filters.command("tts"))
async def tts_command(client, message):
    if len(message.command) < 2:
        await message.reply("Usage: /tts <text>")
        return
    text = " ".join(message.command[1:])
    user_id = message.from_user.id
    # Store user text for later retrieval
    tts_requests[user_id] = text

    # Create inline buttons for each available audio model (sirf model ke naam show ho)
    buttons = []
    for model in available_audio_models:
        buttons.append(
            InlineKeyboardButton(
                text=model["caption"],
                callback_data=f"tts_model:{model['id']}"
            )
        )
    keyboard = InlineKeyboardMarkup([buttons])
    # Message text mein hi "Select an audio model:" show hoga
    await message.reply("Select an audio model:", reply_markup=keyboard)

# Callback query handler for audio model selection
@app.on_callback_query(filters.regex(r"^tts_model:"))
async def tts_model_callback(client, callback_query):
    # Extract selected model id from callback data
    selected_model = callback_query.data.split(":", 1)[1]
    user_id = callback_query.from_user.id

    # Retrieve stored text; agar na mile toh error show karo
    if user_id not in tts_requests:
        await callback_query.answer("No TTS request found.", show_alert=True)
        return
    text = tts_requests.pop(user_id)  # Remove stored text after retrieving

    # Edit the message to show waiting message and remove inline buttons
    await callback_query.message.edit_text("Audio generation in progress. Please wait...")

    # Build TTS API URL with text and selected model
    base_url = f"{IMG_GEN_API}/get-audio"
    params = {
        "text": text,
        "model": selected_model
    }
    query_string = urllib.parse.urlencode(params)
    url = f"{base_url}?{query_string}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                audio_bytes = await resp.read()
                audio_file = io.BytesIO(audio_bytes)
                audio_file.name = "speech.mp3"
                # Delete the waiting message
                await callback_query.message.delete()
                # Send the generated audio to the user
                await client.send_audio(
                    callback_query.message.chat.id,
                    audio_file,
                    caption="Text-to-Speech Generated!"
                )
            else:
                await callback_query.message.edit_text(f"Error: API returned status {resp.status}")
