import asyncio
import aiohttp
import json
import os
import time
import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# Assuming you have a file named DURGESH.py where your Pyrogram app is initialized.
from DURGESH import app

# A temporary cache to store media info for downloads
# The key will be the callback_data from the button
media_cache = {}


@app.on_message(filters.command("yt"))
async def yt_command_handler(client: Client, message: Message):
    """
    Handles the /yt command. Fetches media info using yt-dlp and presents download buttons.
    """
    if len(message.command) < 2:
        await message.reply_text("Please provide a YouTube URL after the command.\n\nExample: `/yt https://www.youtube.com/watch?v=dQw4w9WgXcQ`")
        return

    youtube_url = message.command[1]
    
    processing_message = await message.reply_text("`Fetching formats, please wait...`")

    try:
        # Use yt-dlp to extract video information without downloading
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, youtube_url, download=False)

    except Exception as e:
        await processing_message.edit_text(f"**An error occurred while fetching video info:**\n`{e}`")
        return

    best_video = None
    best_audio = None
    max_height = 0
    max_abr = 0

    # Find the best video-only and audio-only formats
    for f in info.get('formats', []):
        if f.get('vcodec') != 'none' and f.get('acodec') == 'none' and f.get('ext') == 'mp4':
            height = f.get('height', 0)
            if height > max_height:
                max_height = height
                best_video = f
        
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none' and 'm4a' in f.get('ext', ''):
            abr = f.get('abr', 0)
            if abr > max_abr:
                max_abr = abr
                best_audio = f

    if not best_video and not best_audio:
        await processing_message.edit_text("Could not find any suitable video or audio streams for the provided URL.")
        return

    # Prepare the response text and buttons
    response_text = f"**{info.get('title', 'Video')}**\n\n"
    buttons = []
    
    if best_video:
        filesize = best_video.get('filesize') or best_video.get('filesize_approx')
        formatted_size = f"{filesize / (1024*1024):.2f} MB" if filesize else "N/A"
        response_text += (
            f"**🎬 Best Video (No Audio):**\n"
            f"  - **Quality:** `{best_video.get('format_note', 'N/A')}`\n"
            f"  - **Resolution:** `{best_video.get('resolution', 'N/A')}`\n"
            f"  - **Size:** `{formatted_size}`\n\n"
        )
        cache_key = f"dl_video_{message.id}_{int(time.time())}"
        buttons.append(InlineKeyboardButton("Download Video 🎬", callback_data=cache_key))
        media_cache[cache_key] = {'url': youtube_url, 'format_id': best_video['format_id'], 'title': info.get('title', 'video')}

    if best_audio:
        filesize = best_audio.get('filesize') or best_audio.get('filesize_approx')
        formatted_size = f"{filesize / (1024*1024):.2f} MB" if filesize else "N/A"
        response_text += (
            f"**🎵 Best Audio:**\n"
            f"  - **Bitrate:** `{best_audio.get('abr', 0)} kbps`\n"
            f"  - **Size:** `{formatted_size}`\n"
        )
        cache_key = f"dl_audio_{message.id}_{int(time.time())}"
        buttons.append(InlineKeyboardButton("Download Audio 🎵", callback_data=cache_key))
        media_cache[cache_key] = {'url': youtube_url, 'format_id': best_audio['format_id'], 'title': info.get('title', 'audio')}
    
    keyboard = [buttons] if len(buttons) <= 2 else [[b] for b in buttons]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await processing_message.edit_text(
        response_text,
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

async def progress_callback(current, total, message):
    """Updates the message with Telegram upload progress."""
    try:
        # Edit message only every few seconds to avoid API spam
        current_time = time.time()
        if not hasattr(progress_callback, "last_edit") or (current_time - progress_callback.last_edit) > 3:
            await message.edit_text(f"`Uploading... {current * 100 / total:.1f}%`")
            progress_callback.last_edit = current_time
    except Exception:
        pass

@app.on_callback_query(filters.regex("^dl_"))
async def download_handler(client: Client, callback_query: CallbackQuery):
    """Handles the download button clicks using yt-dlp."""
    cache_key = callback_query.data
    media_info = media_cache.get(cache_key)
    
    if not media_info:
        await callback_query.message.edit_text("Sorry, this download link has expired or is invalid.")
        await callback_query.answer("Link expired.", show_alert=True)
        return

    await callback_query.answer("Request received. Starting download...", show_alert=False)
    
    media_type = "video" if "video" in cache_key else "audio"
    youtube_url = media_info['url']
    format_id = media_info['format_id']
    title = media_info.get('title', 'media').replace('/', '_').replace(':', '_')
    
    download_dir = "downloads"
    if not os.path.isdir(download_dir):
        os.makedirs(download_dir)

    # Use a predictable filename to easily find the downloaded file
    base_filename = f"{title[:50]}_{cache_key}"
    file_path_template = os.path.join(download_dir, f"{base_filename}.%(ext)s")
    
    downloaded_file = None
    try:
        # Progress hook for yt-dlp to show download progress
        async def ytdl_progress_hook(d):
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                if total_bytes:
                    downloaded_bytes = d.get('downloaded_bytes', 0)
                    percentage = downloaded_bytes * 100 / total_bytes
                    current_time = time.time()
                    if not hasattr(ytdl_progress_hook, "last_edit") or (current_time - ytdl_progress_hook.last_edit) > 3:
                        try:
                            await callback_query.message.edit_text(f"`Downloading {media_type}... {percentage:.1f}%`")
                            ytdl_progress_hook.last_edit = current_time
                        except Exception:
                            pass

        ydl_opts = {
            'format': format_id,
            'outtmpl': file_path_template,
            'progress_hooks': [ytdl_progress_hook],
            'noprogress': True,
        }

        await callback_query.message.edit_text(f"`Downloading {media_type}... Please wait.`")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [youtube_url])

        # Find the exact name of the downloaded file
        for f in os.listdir(download_dir):
            if f.startswith(base_filename):
                downloaded_file = os.path.join(download_dir, f)
                break
        
        if not downloaded_file:
            await callback_query.message.edit_text("Error: Downloaded file not found on server.")
            return

        await callback_query.message.edit_text(f"`Download complete. Uploading to Telegram...`")

        if media_type == "video":
            await client.send_video(
                chat_id=callback_query.message.chat.id, video=downloaded_file,
                caption=title, progress=progress_callback, progress_args=(callback_query.message,)
            )
        else:
            await client.send_audio(
                chat_id=callback_query.message.chat.id, audio=downloaded_file,
                caption=title, progress=progress_callback, progress_args=(callback_query.message,)
            )
        
        await callback_query.message.delete()

    except Exception as e:
        print(f"Error during download/upload: {e}")
        await callback_query.message.edit_text(f"**An error occurred:**\n`{e}`")
    finally:
        if downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)
        if cache_key in media_cache:
            del media_cache[cache_key]

