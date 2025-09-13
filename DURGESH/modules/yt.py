import asyncio
import aiohttp
import json
import os
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# Assuming you have a file named DURGESH.py where your Pyrogram app is initialized.
from DURGESH import app

# A temporary cache to store media info for downloads
# The key will be the callback_data from the button
media_cache = {}

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
    Handles the /yt command. Fetches media info and presents download buttons.
    """
    if len(message.command) < 2:
        await message.reply_text("Please provide a YouTube URL after the command.\n\nExample: `/yt https://www.youtube.com/watch?v=dQw4w9WgXcQ`")
        return

    youtube_url = message.command[1]
    
    processing_message = await message.reply_text("`Fetching media details, please wait...`")

    best_video, best_audio, error = await get_best_media(youtube_url)

    if error:
        await processing_message.edit_text(f"**An error occurred:**\n`{error}`")
        return

    if not best_video and not best_audio:
        await processing_message.edit_text("Could not find any suitable video or audio streams for the provided URL.")
        return

    # Prepare the response text and buttons
    response_text = "**Found Best Media Streams!**\n\n"
    buttons = []
    
    if best_video:
        response_text += (
            f"**🎬 Best Video (No Audio):**\n"
            f"  - **Quality:** `{best_video.get('quality', 'N/A')}`\n"
            f"  - **Resolution:** `{best_video.get('width', 'N/A')}x{best_video.get('height', 'N/A')}`\n"
            f"  - **Size:** `{best_video.get('formattedSize', 'N/A')}`\n\n"
        )
        # Unique callback data to act as a key for our cache
        cache_key = f"dl_video_{message.id}_{int(time.time())}"
        buttons.append(
            InlineKeyboardButton("Download Video 🎬", callback_data=cache_key)
        )
        media_cache[cache_key] = best_video

    if best_audio:
        response_text += (
            f"**🎵 Best Audio:**\n"
            f"  - **Bitrate:** `{best_audio.get('bitrate', 'N/A')} kbps`\n"
            f"  - **Size:** `{best_audio.get('formattedSize', 'N/A')}`\n"
        )
        cache_key = f"dl_audio_{message.id}_{int(time.time())}"
        buttons.append(
            InlineKeyboardButton("Download Audio 🎵", callback_data=cache_key)
        )
        media_cache[cache_key] = best_audio
    
    # Create rows of buttons
    keyboard = [buttons] if len(buttons) <= 2 else [[b] for b in buttons]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await processing_message.edit_text(
        response_text,
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

async def progress_callback(current, total, message):
    """Updates the message with upload progress."""
    try:
        await message.edit_text(f"`Uploading... {current * 100 / total:.1f}%`")
    except asyncio.exceptions.TimeoutError:
        pass # Ignore if editing times out
    except Exception:
        pass # Ignore other potential errors like message not modified

@app.on_callback_query(filters.regex("^dl_"))
async def download_handler(client: Client, callback_query: CallbackQuery):
    """Handles the download button clicks."""
    cache_key = callback_query.data
    media_info = media_cache.get(cache_key)
    
    if not media_info:
        await callback_query.message.edit_text("Sorry, this download link has expired or is invalid.")
        await callback_query.answer("Link expired.", show_alert=True)
        return

    await callback_query.answer("Request received. Starting download...", show_alert=False)
    
    media_type = "video" if "video" in cache_key else "audio"
    download_url = media_info.get("url")
    
    # Generate a safe filename
    title = media_info.get('title', 'media').replace('/', '_').replace(':', '_')
    quality = media_info.get('quality', 'audio')
    ext = media_info.get('ext', 'mp4')
    file_name = f"{title[:50]}_{quality}.{ext}"
    
    download_dir = "downloads"
    if not os.path.isdir(download_dir):
        os.makedirs(download_dir)
    file_path = os.path.join(download_dir, file_name)

    try:
        await callback_query.message.edit_text(f"`Downloading {media_type}... Please wait.`")
        
        # Download the file using aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url) as resp:
                if resp.status == 200:
                    with open(file_path, 'wb') as f:
                        while True:
                            chunk = await resp.content.read(4096)
                            if not chunk:
                                break
                            f.write(chunk)
                else:
                    await callback_query.message.edit_text("Failed to download the file. The link might be broken.")
                    return

        await callback_query.message.edit_text(f"`Download complete. Uploading to Telegram...`")

        # Upload to Telegram
        if media_type == "video":
            await client.send_video(
                chat_id=callback_query.message.chat.id,
                video=file_path,
                caption=f"{media_info.get('title', 'Video')}",
                progress=progress_callback,
                progress_args=(callback_query.message,)
            )
        else: # audio
            await client.send_audio(
                chat_id=callback_query.message.chat.id,
                audio=file_path,
                caption=f"{media_info.get('title', 'Audio')}",
                progress=progress_callback,
                progress_args=(callback_query.message,)
            )
        
        await callback_query.message.delete()

    except Exception as e:
        print(f"Error during download/upload: {e}")
        await callback_query.message.edit_text(f"**An error occurred:**\n`{e}`")
    finally:
        # Clean up the downloaded file and cache
        if os.path.exists(file_path):
            os.remove(file_path)
        if cache_key in media_cache:
            del media_cache[cache_key]

