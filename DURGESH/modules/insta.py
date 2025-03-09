import re, os
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from DURGESH import app
import instaloader

@app.on_message(filters.text & filters.regex(r"^(https?://)?(www\.)?(instagram\.com|instagr\.am)/.*$"))
async def auto_download_instagram_video(client, message):
    url = message.text.strip()
    status_msg = await message.reply_text("ᴘʀᴏᴄᴇssɪɴɢ...")
    
    # Instagram URL se shortcode extract karo
    match = re.search(r"instagram\.com/p/([^/]+)/", url)
    if not match:
        await status_msg.edit("Invalid Instagram URL.")
        return
    shortcode = match.group(1)
    
    try:
        # Instaloader object initialize karo
        L = instaloader.Instaloader(dirname_pattern="downloads", filename_pattern="{shortcode}")
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        if not post.is_video:
            await status_msg.edit("Yeh post video nahi hai.")
            return
        
        # Post ko download karo
        L.download_post(post, target="downloads")
        
        # Expected file path
        video_path = f"downloads/{shortcode}.mp4"
        if not os.path.exists(video_path):
            for file in os.listdir("downloads"):
                if file.startswith(shortcode) and file.endswith(".mp4"):
                    video_path = os.path.join("downloads", file)
                    break
        
        caption = (
            f"Dᴜʀᴀᴛɪᴏɴ: {post.video_duration} sec\n"
            f"User: {post.owner_username}\n"
            f"Shortcode: {post.shortcode}"
        )
        
        await status_msg.delete()
        await message.reply_video(video_path, caption=caption)
        
        # Clean up: file delete karo
        os.remove(video_path)
        
    except Exception as e:
        await status_msg.edit(f"Error: {str(e)}")
