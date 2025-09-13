import aiohttp
from pyrogram import Client, filters
from pyrogram.types import Message
from DURGESH import app

async def get_youtube_stream(video_url):
    API_URL = "https://www.clipto.com/api/youtube"
    async with aiohttp.ClientSession() as session:
        payload = {"url": video_url}
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/plain, */*", "User-Agent": "Mozilla/5.0"}
        try:
            async with session.post(API_URL, json=payload, headers=headers) as resp:
                if resp.status != 200: return None
                data = await resp.json()
        except: return None
    medias = data.get("medias", [])
    best_video = max([m for m in medias if m.get("type") == "video"], key=lambda x: x.get("height", 0), default=None)
    best_audio = max([m for m in medias if m.get("type") == "audio"], key=lambda x: x.get("bitrate", 0), default=None)
    return {
        "title": data.get("title"),
        "video_url": best_video["url"] if best_video else None,
        "audio_url": best_audio["url"] if best_audio else None
    }

@app.on_message(filters.command("yt"))
async def yt_handler(client, message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Send YouTube URL like: /yt https://youtube.com/watch?v=...")
    url = message.command[1]
    if "youtube.com" not in url and "youtu.be" not in url:
        return await message.reply_text("❌ Invalid YouTube link.")
    await client.send_chat_action(message.chat.id, "typing")
    result = await get_youtube_stream(url)
    if not result or not result.get("title"):
        return await message.reply_text("❌ Failed to fetch video info.")
    title = result["title"]
    v = result["video_url"] or "Not available"
    a = result["audio_url"] or "Not available"
    text = f"🎬 {title}\n\n🎥 Video: {v}\n🎵 Audio: {a}\n\n💡 Click to download."
    await message.reply_text(text, disable_web_page_preview=True, parse_mode="markdown")
