from pyrogram import Client, filters, enums
import requests
import urllib.parse
import asyncio
from DURGESH import app  # Ensure this exists and is configured correctly


# Function to query the AI API
def ask_query(query: str) -> str:
    try:
        url = f"https://chatwithai.codesearch.workers.dev/?chat={urllib.parse.quote(query)}"
        response = requests.get(url)

        if response.status_code == 200:
            return response.json().get("data", "I couldn't find an answer to that.")
        return f"⚠️ API error: {response.status_code}"
    
    except Exception as e:
        return f"⚠️ Unexpected error: {e}"


# Function to simulate typing action
async def send_typing_action(client: Client, chat_id: int, duration: int = 2):
    await client.send_chat_action(chat_id, enums.ChatAction.TYPING)
    await asyncio.sleep(duration)


# Handler for "/ask" command
@app.on_message(filters.command("ask"))
async def handle_query(client: Client, message):
    if len(message.command) < 2:
        await message.reply_text("💡 Please provide a question.")
        return

    user_query = message.text.split(" ", 1)[1]

    await send_typing_action(client, message.chat.id)
    response = ask_query(user_query)

    await message.reply_text(response)