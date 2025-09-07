from pyrogram import filters
from DURGESH import app
import requests
import os
import tempfile
import shutil
import yt_dlp
import asyncio

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

        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        
        try:
            # yt-dlp options for best quality
            ydl_opts = {
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
            }

            await processing_msg.edit_text("🔍 **Fetching video info...**")
            
            # Get video info
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)
                
                # Download video
                await processing_msg.edit_text("📥 **Downloading video...**")
                ydl.download([youtube_url])
            
            # Find downloaded file
            downloaded_files = os.listdir(temp_dir)
            if not downloaded_files:
                await processing_msg.edit_text("❌ **Error:** Download failed")
                return
            
            video_path = os.path.join(temp_dir, downloaded_files[0])
            
            # Check file size
            if os.path.getsize(video_path) == 0:
                await processing_msg.edit_text("❌ **Error:** Empty file downloaded")
                return
            
            # Send video file
            await processing_msg.edit_text("📤 **Uploading video...**")
            
            if video_path.endswith('.mp4') or video_path.endswith('.mkv') or video_path.endswith('.webm'):
                await message.reply_video(
                    video=video_path,
                    caption=f"🎬 **{title}**\n⏰ Duration: {duration}s",
                    supports_streaming=True
                )
            else:
                await message.reply_document(
                    document=video_path,
                    caption=f"🎬 **{title}**\n⏰ Duration: {duration}s"
                )
            
            await processing_msg.delete()

        except yt_dlp.utils.DownloadError as e:
            await processing_msg.edit_text(f"❌ **Download Error:** {str(e)}")
        except Exception as e:
            await processing_msg.edit_text(f"❌ **Error:** {str(e)}")
        finally:
            # Cleanup temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        await message.reply_text(f"❌ **Main Error:** {str(e)}")

# Audio only download
@app.on_message(filters.command("daudio"))
async def download_youtube_audio(client, message):
    try:
        if len(message.command) < 2:
            await message.reply_text("**Usage:** `/daudio youtube_link`")
            return

        youtube_url = message.command[1]
        processing_msg = await message.reply_text("📥 **Processing audio...**")
        temp_dir = tempfile.mkdtemp()
        
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                title = info.get('title', 'Unknown Title')
                duration = info.get('duration', 0)
                
                await processing_msg.edit_text("🎵 **Downloading audio...**")
                ydl.download([youtube_url])
            
            # Find MP3 file
            mp3_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
            if not mp3_files:
                await processing_msg.edit_text("❌ **Error:** Audio download failed")
                return
            
            audio_path = os.path.join(temp_dir, mp3_files[0])
            
            await processing_msg.edit_text("📤 **Uploading audio...**")
            await message.reply_audio(
                audio=audio_path,
                caption=f"🎵 **{title}**\n⏰ Duration: {duration}s",
                title=title[:30]
            )
            
            await processing_msg.delete()

        except Exception as e:
            await processing_msg.edit_text(f"❌ **Error:** {str(e)}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        await message.reply_text(f"❌ **Error:** {str(e)}")
