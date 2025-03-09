import re
import os
from pyrogram import filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from DURGESH import app
import instaloader

# Ensure "downloads" folder exists
os.makedirs("downloads", exist_ok=True)

# Updated regex pattern to match posts, reels, and tv URLs
regex_pattern = r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)"

@app.on_message(filters.text & filters.regex(regex_pattern))
async def auto_download_instagram_media(client, message):
    url = message.text.strip()
    status_msg = await message.reply_text("ᴘʀᴏᴄᴇssɪɴɢ...")
    
    # Extract shortcode using updated regex
    match = re.search(regex_pattern, url)
    if not match:
        await status_msg.edit("Invalid Instagram URL.")
        return
    shortcode = match.group(1)
    
    try:
        # Debug: Print shortcode for verification
        print(f"Extracted shortcode: {shortcode}")
        
        # Initialize Instaloader with custom folder & filename pattern
        L = instaloader.Instaloader(dirname_pattern="downloads", filename_pattern="{shortcode}")
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Debug: Print post type
        print(f"Post typename: {post.typename}")
        
        # Check if the post is downloadable (for private posts login chahiye)
        # Agar public hai to download_post kaam karega
        L.download_post(post, target="downloads")
        
        # After download, list downloaded files for debugging
        downloaded_files = [f for f in os.listdir("downloads") if f.startswith(shortcode)]
        print("Downloaded files:", downloaded_files)
        
        if not downloaded_files:
            await status_msg.edit("Download failed. No files found.")
            return
        
        # Handling different post types
        if post.typename == "GraphSidecar":
            # Multiple media post
            media_group = []
            for file in sorted(downloaded_files):
                file_path = os.path.join("downloads", file)
                ext = os.path.splitext(file)[1].lower()
                if ext in [".mp4"]:
                    media_group.append(InputMediaVideo(media=file_path))
                elif ext in [".jpg", ".jpeg", ".png"]:
                    media_group.append(InputMediaPhoto(media=file_path))
            if media_group:
                await status_msg.delete()
                await message.reply_media_group(media=media_group)
            else:
                await status_msg.edit("No media files found in the post.")
                
        elif post.typename == "GraphVideo":
            # Single video post
            video_file = None
            for file in downloaded_files:
                if file.lower().endswith(".mp4"):
                    video_file = os.path.join("downloads", file)
                    break
            if not video_file:
                await status_msg.edit("Video file not found.")
                return
            caption = (
                f"User: {post.owner_username}\n"
                f"Shortcode: {post.shortcode}\n"
                f"Duration: {post.video_duration} sec"
            )
            await status_msg.delete()
            await message.reply_video(video_file, caption=caption)
            
        elif post.typename == "GraphImage":
            # Single image post
            image_file = None
            for file in downloaded_files:
                if file.lower().endswith((".jpg", ".jpeg", ".png")):
                    image_file = os.path.join("downloads", file)
                    break
            if not image_file:
                await status_msg.edit("Image file not found.")
                return
            caption = (
                f"User: {post.owner_username}\n"
                f"Shortcode: {post.shortcode}"
            )
            await status_msg.delete()
            await message.reply_photo(image_file, caption=caption)
            
        else:
            await status_msg.edit("Unsupported media type.")
            return
        
        # Clean up: Delete all files that start with the shortcode
        for file in downloaded_files:
            os.remove(os.path.join("downloads", file))
                
    except Exception as e:
        await status_msg.edit(f"Error: {str(e)}")
