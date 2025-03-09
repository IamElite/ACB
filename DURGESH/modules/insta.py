import re
import os
from pyrogram import filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from DURGESH import app
import instaloader

# Ensure "downloads" folder exists
os.makedirs("downloads", exist_ok=True)

# Improved regex pattern to extract shortcode from Instagram URL
regex_pattern = r"instagram\.com/p/([^/?#&]+)"

@app.on_message(filters.text & filters.regex(regex_pattern))
async def auto_download_instagram_media(client, message):
    url = message.text.strip()
    status_msg = await message.reply_text("ᴘʀᴏᴄᴇssɪɴɢ...")
    
    # Shortcode extract karo
    match = re.search(regex_pattern, url)
    if not match:
        await status_msg.edit("Invalid Instagram URL.")
        return
    shortcode = match.group(1)
    
    try:
        # Instaloader object initialize karo with custom folder & filename pattern
        L = instaloader.Instaloader(dirname_pattern="downloads", filename_pattern="{shortcode}")
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Post download karo; agar sidecar hai toh sab media download honge
        L.download_post(post, target="downloads")
        
        if post.typename == "GraphSidecar":
            # Multiple media: downloads folder se sab files gather karo jo shortcode se start hoti hain
            files = []
            for file in os.listdir("downloads"):
                if file.startswith(shortcode):
                    files.append(os.path.join("downloads", file))
            files.sort()  # order maintain karne ke liye
            
            media_group = []
            for file_path in files:
                ext = os.path.splitext(file_path)[1].lower()
                if ext in [".mp4"]:
                    media_group.append(InputMediaVideo(media=file_path))
                elif ext in [".jpg", ".jpeg", ".png"]:
                    media_group.append(InputMediaPhoto(media=file_path))
            if media_group:
                await status_msg.delete()
                await message.reply_media_group(media=media_group)
            else:
                await status_msg.edit("No media files found.")
                
        elif post.typename == "GraphVideo":
            # Single video post
            video_path = os.path.join("downloads", f"{shortcode}.mp4")
            if not os.path.exists(video_path):
                for file in os.listdir("downloads"):
                    if file.startswith(shortcode) and file.endswith(".mp4"):
                        video_path = os.path.join("downloads", file)
                        break
            caption = (
                f"User: {post.owner_username}\n"
                f"Shortcode: {post.shortcode}\n"
                f"Duration: {post.video_duration} sec"
            )
            await status_msg.delete()
            await message.reply_video(video_path, caption=caption)
            
        elif post.typename == "GraphImage":
            # Single image post
            image_path = os.path.join("downloads", f"{shortcode}.jpg")
            if not os.path.exists(image_path):
                for file in os.listdir("downloads"):
                    if file.startswith(shortcode) and file.lower().endswith((".jpg", ".jpeg", ".png")):
                        image_path = os.path.join("downloads", file)
                        break
            caption = (
                f"User: {post.owner_username}\n"
                f"Shortcode: {post.shortcode}"
            )
            await status_msg.delete()
            await message.reply_photo(image_path, caption=caption)
        else:
            await status_msg.edit("Unsupported media type.")
        
        # Cleanup: downloads folder se sab files jo shortcode se start hote hain, remove karo
        for file in os.listdir("downloads"):
            if file.startswith(shortcode):
                os.remove(os.path.join("downloads", file))
                
    except Exception as e:
        await status_msg.edit(f"Error: {str(e)}")

