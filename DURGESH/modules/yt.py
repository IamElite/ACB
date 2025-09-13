from pyrogram import filters
from DURGEHS import app  # your existing Pyrogram Client
import aiohttp
import asyncio
import os

# --- Clipto Stream Fetcher ---
async def get_youtube_stream(video_url: str):
    API_URL = "https://www.clipto.com/api/youtube"
    async with aiohttp.ClientSession() as session:
        payload = {"url": video_url}
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0",
        }
        async with session.post(API_URL, json=payload, headers=headers) as resp:
            data = await resp.json()

    medias = data.get("medias", [])
    best_video = max([m for m in medias if m.get("type") == "video"], key=lambda x: x.get("height", 0), default=None)
    best_audio = max([m for m in medias if m.get("type") == "audio"], key=lambda x: x.get("bitrate", 0), default=None)

    return {
        "title": data.get("title"),
        "video_url": best_video["url"] if best_video else None,
        "audio_url": best_audio["url"] if best_audio else None
    }

# --- Downloader ---
async def download_file(url, filename):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                with open(filename, "wb") as f:
                    f.write(await resp.read())
                return filename
            return None

# --- /ty Command Handler ---
@app.on_message(filters.command("yt"))
async def ty_handler(client, message):
    if len(message.command) < 2:
        return await message.reply_text("⚠️ Usage: `/ty <YouTube_URL>`", quote=True)

    url = message.command[1]
    status = await message.reply_text("⏳ Fetching stream...")

    try:
        data = await get_youtube_stream(url)
        title = data.get("title") or "Stream"

        if not data["video_url"]:
            return await status.edit("❌ No video stream found.")

        filename = f"{title}.mp4".replace(" ", "_").replace("/", "_")
        await status.edit("📥 Downloading best video...")

        file_path = await download_file(data["video_url"], filename)
        if not file_path:
            return await status.edit("❌ Download failed.")

        await status.edit("📤 Uploading to Telegram...")
        await message.reply_video(file_path, caption=f"🎬 **{title}**", quote=True)
        os.remove(file_path)

    except Exception as e:
        await status.edit(f"❌ Error: `{e}`")
