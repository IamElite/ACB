import re
import os
from pyrogram import filters
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from DURGESH import app
import instaloader

# Ensure "downloads" folder exists
os.makedirs("downloads", exist_ok=True)

# Regex pattern jo posts, reels, aur IGTV URLs match kare
regex_pattern = r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)"

@app.on_message(filters.text & filters.regex(regex_pattern))
async def auto_download_instagram_media(client, message):
    url = message.text.strip()
    status_msg = await message.reply_text("ᴘʀᴏᴄᴇssɪɴɢ...")
    
    # Shortcode extract karo using updated regex
    match = re.search(regex_pattern, url)
    if not match:
        await status_msg.edit("Invalid Instagram URL.")
        return
    shortcode = match.group(1)
    
    try:
        print(f"Extracted shortcode: {shortcode}")
        # Initialize instaloader with downloads folder and filename pattern
        L = instaloader.Instaloader(dirname_pattern="downloads", filename_pattern="{shortcode}")
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        print(f"Post typename: {post.typename}")
        
        # Download post media (sidecar, video, or image)
        L.download_post(post, target="downloads")
        
        # List downloaded files for given shortcode
        downloaded_files = [f for f in os.listdir("downloads") if f.startswith(shortcode)]
        print("Downloaded files:", downloaded_files)
        
        if not downloaded_files:
            await status_msg.edit("Download failed. No files found.")
            return
        
        chat_id = message.chat.id
        # For channels, reply_to_message_id set nahi karenge
        reply_to = message.message_id if message.chat.type != "channel" else None
        
        # Prepare caption text (improved)
        if post.typename == "GraphVideo":
            caption = (
                f"📹 *Instagram Video*\n"
                f"👤 *User:* {post.owner_username}\n"
                f"⏱ *Duration:* {post.video_duration} sec\n"
                f"🔗 *Shortcode:* {post.shortcode}\n\n"
                f"📥 Downloaded using Instaloader"
            )
            # Find video file
            video_file = None
            for file in downloaded_files:
                if file.lower().endswith(".mp4"):
                    video_file = os.path.join("downloads", file)
                    break
            if not video_file:
                await status_msg.edit("Video file not found.")
                return
            await status_msg.delete()
            await app.send_video(chat_id, video_file, caption=caption, parse_mode="markdown", reply_to_message_id=reply_to)
        
        elif post.typename == "GraphImage":
            caption = (
                f"📸 *Instagram Post*\n"
                f"👤 *User:* {post.owner_username}\n"
                f"🔗 *Shortcode:* {post.shortcode}\n\n"
                f"📥 Downloaded using Instaloader"
            )
            image_file = None
            for file in downloaded_files:
                if file.lower().endswith((".jpg", ".jpeg", ".png")):
                    image_file = os.path.join("downloads", file)
                    break
            if not image_file:
                await status_msg.edit("Image file not found.")
                return
            await status_msg.delete()
            await app.send_photo(chat_id, image_file, caption=caption, parse_mode="markdown", reply_to_message_id=reply_to)
        
        elif post.typename == "GraphSidecar":
            # Multiple media post: ek media group bhejte hain; caption pehle media item mein set karenge
            media_group = []
            for file in sorted(downloaded_files):
                file_path = os.path.join("downloads", file)
                ext = os.path.splitext(file)[1].lower()
                if ext in [".mp4"]:
                    media_group.append(InputMediaVideo(media=file_path))
                elif ext in [".jpg", ".jpeg", ".png"]:
                    media_group.append(InputMediaPhoto(media=file_path))
            if media_group:
                media_group[0].caption = (
                    f"📸 *Instagram Sidecar*\n"
                    f"👤 *User:* {post.owner_username}\n"
                    f"🔗 *Shortcode:* {post.shortcode}\n\n"
                    f"📥 Downloaded using Instaloader"
                )
                media_group[0].parse_mode = "markdown"
                await status_msg.delete()
                await app.send_media_group(chat_id, media=media_group)
            else:
                await status_msg.edit("No media files found in the post.")
                return
        
        else:
            await status_msg.edit("Unsupported media type.")
            return
        
        # Cleanup: Delete downloaded files
        for file in downloaded_files:
            os.remove(os.path.join("downloads", file))
                
    except Exception as e:
        await status_msg.edit(f"Error: {str(e)}")
