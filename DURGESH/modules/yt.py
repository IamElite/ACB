import asyncio
import aiohttp
import json
from pyrogram import Client, filters
from pyrogram.types import Message

# Assuming you have a file named DURGESH.py where your Pyrogram app is initialized.
from DURGESH import app

async def get_best_media(youtube_url: str):
    """
    Fetches the best video and audio streams for a given YouTube URL from the clipto.com API.
    """
    api_url = "https://www.clipto.com/api/youtube"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }
    payload = {"url": youtube_url}

    best_video = None
    best_audio = None

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(api_url, json=payload) as response:
                if response.status != 200:
                    print(f"Error: API returned status code {response.status}.")
                    return None, None, f"API returned status code {response.status}"

                data = await response.json()

                if not data.get("success"):
                    print("Error: API request was not successful.")
                    return None, None, "API request was not successful."

                # Find the best video stream (mp4, no audio)
                max_height = 0
                for media in data.get("medias", []):
                    if media.get("type") == "video" and media.get("ext") == "mp4" and media.get("audioQuality") is None:
                        height = media.get("height", 0)
                        if height > max_height:
                            max_height = height
                            best_video = media

                # Find the best audio stream
                max_bitrate = 0
                for media in data.get("medias", []):
                    if media.get("type") == "audio":
                        bitrate = media.get("bitrate", 0)
                        if bitrate > max_bitrate:
                            max_bitrate = bitrate
                            best_audio = media
                
                return best_video, best_audio, None

    except aiohttp.ClientError as e:
        print(f"An error occurred while sending the request: {e}")
        return None, None, f"An error occurred: {e}"
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None, None, f"An unexpected error occurred: {e}"


@app.on_message(filters.command("yt"))
async def yt_command_handler(client: Client, message: Message):
    """
    Handles the /yt command.
    """
    if len(message.command) < 2:
        await message.reply_text("Please provide a YouTube URL after the command.\n\nExample: `/yt https://www.youtube.com/watch?v=dQw4w9WgXcQ`")
        return

    youtube_url = message.command[1]
    
    # Send a processing message
    processing_message = await message.reply_text("`Fetching media details, please wait...`")

    best_video, best_audio, error = await get_best_media(youtube_url)

    if error:
        await processing_message.edit_text(f"**An error occurred:**\n`{error}`")
        return

    if not best_video and not best_audio:
        await processing_message.edit_text("Could not find any suitable video or audio streams for the provided URL.")
        return

    # Prepare the response text
    response_text = "**Found Best Media Streams!**\n\n"
    
    if best_video:
        response_text += (
            f"**🎬 Best Video (No Audio):**\n"
            f"  - **Quality:** `{best_video.get('quality', 'N/A')}`\n"
            f"  - **Resolution:** `{best_video.get('width', 'N/A')}x{best_video.get('height', 'N/A')}`\n"
            f"  - **Size:** `{best_video.get('formattedSize', 'N/A')}`\n"
            f"  - **URL:** [Click to view]({best_video.get('url')})\n\n"
        )
    else:
        response_text += "**🎬 Best Video (No Audio):**\n  - Not found.\n\n"

    if best_audio:
        response_text += (
            f"**🎵 Best Audio:**\n"
            f"  - **Bitrate:** `{best_audio.get('bitrate', 'N/A')} kbps`\n"
            f"  - **Size:** `{best_audio.get('formattedSize', 'N/A')}`\n"
            f"  - **URL:** [Click to listen]({best_audio.get('url')})\n"
        )
    else:
        response_text += "**🎵 Best Audio:**\n  - Not found.\n"

    # Edit the processing message with the final result
    await processing_message.edit_text(
        response_text,
        disable_web_page_preview=True # To keep the message clean
    )

