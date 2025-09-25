import os
import requests
import yt_dlp
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from DURGESH import app

# YouTube-DL configuration for audio extraction
YDL_OPTS = {
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'outtmpl': 'downloads/%(title)s.%(ext)s'
}

# Store video URLs temporarily (consider using a proper cache system for production)
app._video_urls = {}


@app.on_message(filters.text & filters.regex(r"^(?:https?://)?(?:www\.)?(?:instagram\.com|instagr\.am)/.*$"))
async def auto_download_instagram_video(client, message):
    """Handle Instagram video downloads with audio extraction option."""
    status_msg = await message.reply_text("ᴘʀᴏᴄᴇssɪɴɢ...")
    
    try:
        # Fetch video data from API
        response = requests.get(f"https://insta-dl.hazex.workers.dev/?url={message.text}")
        response.raise_for_status()
        result = response.json()
        
        if result.get("error"):
            raise ValueError("API returned error")
            
        data = result["result"]
        video_url = data["url"]
        
        # Store URL for callback handling
        app._video_urls[str(message.id)] = video_url
        
        # Send video with download button
        caption = (
            f"Dᴜʀᴀᴛɪᴏɴ: {data.get('duration', 'N/A')}\n"
            f"Qᴜᴀʟɪᴛʏ: {data.get('quality', 'N/A')}\n"
            f"Tʏᴘᴇ: {data.get('extension', 'N/A')}"
        )
        
        keyboard = InlineKeyboardMarkup([[
            InlineKeyboardButton("Download Audio 🎵", callback_data=f"audio_{message.id}")
        ]])
        
        await message.reply_video(video_url, caption=caption, reply_markup=keyboard)
        
    except Exception as e:
        await status_msg.edit(f"Error: {str(e)}")
        return
        
    await status_msg.delete()


@app.on_callback_query(filters.regex(r"^audio_(\d+)$"))
async def download_audio(client, callback_query):
    """Handle audio extraction from stored video URL."""
    message_id = callback_query.matches[0].group(1)
    video_url = app._video_urls.get(message_id)
    
    if not video_url:
        await callback_query.answer("Video URL expired. Please try again.", show_alert=True)
        return
    
    try:
        await callback_query.message.reply_text("Downloading audio...")
        
        # Extract and send audio
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(video_url, download=True)
            audio_path = f"downloads/{info['title']}.mp3"
            
            await callback_query.message.reply_audio(
                audio_path,
                title=info['title'],
                performer="Instagram Audio"
            )
            
            # Cleanup
            os.remove(audio_path)
            app._video_urls.pop(message_id, None)
            
        await callback_query.answer("Audio downloaded successfully!")
        
    except Exception as e:
        await callback_query.answer(f"Error: {str(e)}", show_alert=True)
