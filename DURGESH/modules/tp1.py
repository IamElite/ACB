from pyrogram import Client, filters
from DURGESH import app
import requests
import json
import os
import tempfile
import shutil

# Command handler for /d
@app.on_message(filters.command("d"))
async def download_youtube_video(client, message):
    try:
        # Check if user provided link
        if len(message.command) < 2:
            await message.reply_text("**Usage:** `/d youtube_link`")
            return

        youtube_url = message.command[1]
        
        # Show processing message
        processing_msg = await message.reply_text("📥 **Processing your request...**")

        # Tubepilot API request
        api_url = "https://tubepilot.ai/wp-admin/admin-ajax.php"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        data = {
            "action": "youtube_video_info",
            "nonce": "aaaa17a5df",
            "video_url": youtube_url
        }

        # Send POST request
        response = requests.post(api_url, headers=headers, data=data)
        response_data = response.json()

        # Check if request was successful
        if not response_data.get("success"):
            await processing_msg.edit_text("❌ **Error:** Could not fetch video details")
            return

        video_info = response_data["data"]["video_info"]
        
        # Get highest quality video and audio
        formats = video_info["formats"]
        best_video = None
        best_audio = None
        
        # Find highest quality video
        for fmt in formats:
            if not fmt.get("audioOnly"):
                if fmt.get("quality") == 1080:
                    best_video = fmt
                    break
                elif fmt.get("quality") == 720 and not best_video:
                    best_video = fmt
                elif fmt.get("quality") == 480 and not best_video:
                    best_video = fmt
        
        # Find best audio
        for fmt in formats:
            if fmt.get("audioOnly"):
                best_audio = fmt
                break

        # Prepare response
        title = video_info["title"]
        duration = video_info["duration"]
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Download and send video
            if best_video:
                video_url = best_video["url"]
                video_size = best_video["filesize"]
                video_quality = best_video.get("quality", "N/A")
                
                # Download video to temp file
                await processing_msg.edit_text("📥 **Downloading video...**")
                video_path = os.path.join(temp_dir, "video.mp4")
                
                with requests.get(video_url, stream=True) as r:
                    with open(video_path, 'wb') as f:
                        shutil.copyfileobj(r.raw, f)
                
                # Send video file
                await message.reply_video(
                    video=video_path,
                    caption=f"🎬 **{title}**\n📹 Quality: {video_quality}p\n💾 Size: {video_size} bytes",
                    duration=duration
                )
                
                # Remove video temp file
                os.remove(video_path)

            # Download and send audio
            if best_audio:
                audio_url = best_audio["url"]
                audio_size = best_audio["filesize"]
                
                # Download audio to temp file
                await processing_msg.edit_text("🎵 **Downloading audio...**")
                audio_path = os.path.join(temp_dir, "audio.mp3")
                
                with requests.get(audio_url, stream=True) as r:
                    with open(audio_path, 'wb') as f:
                        shutil.copyfileobj(r.raw, f)
                
                # Send audio file
                await message.reply_audio(
                    audio=audio_path,
                    caption=f"🎵 **{title}**\n💾 Size: {audio_size} bytes",
                    duration=duration
                )
                
                # Remove audio temp file
                os.remove(audio_path)

            # Delete processing message
            await processing_msg.delete()

        except Exception as e:
            await message.reply_text(f"❌ **Download Error:** {str(e)}")
        finally:
            # Cleanup: Remove temporary directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        error_msg = await message.reply_text(f"❌ **Error:** {str(e)}")
