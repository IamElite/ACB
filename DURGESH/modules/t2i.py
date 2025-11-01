from DURGESH import app
from pyrogram import filters
import requests

API = "https://txt-2-img-api.durgesh-024.workers.dev/"
VALID_RATIOS = {"9:16", "1:1", "16:9", "4:3", "3:4"}

def get_prompt_ratio(text):
    text = text.replace("/img", "").strip()
    if not text:
        return None, None
    parts = text.split()
    if parts[-1] in VALID_RATIOS:
        return " ".join(parts[:-1]), parts[-1]
    return text, "9:16"

@app.on_message(filters.command("img"))
async def img(client, msg):
    prompt, ratio = get_prompt_ratio(msg.text)
    if not prompt:
        return await msg.reply("Usage: `/img <prompt> [ratio]`\nRatios: 9:16, 1:1, 16:9, 4:3, 3:4")
    try:
        r = requests.get(API, params={"prompt": prompt, "ar": ratio}).json()
        if r.get("status") == "success":
            caption = f"**Prompt:** {r['prompt']}\n**Ratio:** {r['aspect_ratio']}"
            await msg.reply_photo(r["image_link"].strip(), caption=caption)
        else:
            await msg.reply("API failed.")
    except Exception as e:
        await msg.reply(f"Error: {e}")
