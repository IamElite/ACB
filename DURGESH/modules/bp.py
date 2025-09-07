from DURGESH import app
from pyrogram import filters
import requests, json

def bypass_url(url):
    try:
        res = requests.post(
            "https://freeseptemberapi.vercel.app/bypass",
            json={"url": url.strip()}
        )
        data = res.text
        if "message" in data:
            return data
        json_data = json.loads(data)
        return json_data.get("url", "No bypassed URL found.")
    except Exception as e:
        return f"Error: {str(e)}"

@app.on_message(filters.command("b"))
def bypass_handler(client, message):
    if len(message.command) < 2:
        message.reply("Please provide a URL after /b command.")
        return

    url = message.command[1]
    bypassed = bypass_url(url)
    message.reply(f"**Bypassed URL:**\n\n{bypassed}")
