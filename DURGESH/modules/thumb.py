import re, subprocess, os, asyncio, urllib.request
from pyrogram import Client, filters
from DURGESH import app
from config import ADMINS
import yt_dlp

def extract_video_ids(url):
    """Extract video IDs from a YouTube URL (single video or playlist)"""
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:  # This is a playlist
                return [entry['id'] for entry in info['entries'] if entry]
            else:  # This is a single video
                return [info['id']]
                
    except Exception as e:
        print(f"Error extracting video IDs: {e}")
        return None

def get_best_thumb(video_id):
    """Get the best thumbnail for a YouTube video ID"""
    return f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"

async def process_and_send_thumb(m, video_id, index=None):
    """Process a single thumbnail and send it"""
    thumb_url = get_best_thumb(video_id)
    
    try:
        img = urllib.request.urlopen(thumb_url).read()
        infile, outfile = f"in_{video_id}.jpg", f"out_{video_id}.jpg"
        
        with open(infile, "wb") as f:
            f.write(img)
            
        subprocess.run([
            "convert", infile,
            "-modulate", "100,115",
            "-sigmoidal-contrast", "4x50%",
            "-enhance",
            "-contrast-stretch", "0.5%x0.5%",
            outfile
        ], check=True)
        
        with open(outfile, "rb") as f:
            caption = f"Video {index+1}" if index is not None else None
            await m.reply_photo(f, caption=caption)
            
        # Clean up
        for f in (infile, outfile):
            if os.path.exists(f):
                os.remove(f)
                
        return True
        
    except Exception as e:
        print(f"Error processing thumbnail: {e}")
        try:
            # Fallback: send original thumbnail
            await m.reply_photo(thumb_url, caption=f"Video {index+1}" if index is not None else None)
            return True
        except:
            return False

@app.on_message(filters.command(["thumbnail","thumb","t"], prefixes=["/","!",".", ""]) & filters.user(ADMINS))
async def send_thumb(_, m):
    # Extract URL from message or reply
    if m.reply_to_message and m.reply_to_message.text:
        url = m.reply_to_message.text.strip()
        args = m.text.split()[1:] if len(m.text.split()) > 1 else []
    else:
        parts = m.text.split()
        url = parts[1] if len(parts) > 1 else None
        args = parts[2:] if len(parts) > 2 else []
    
    if not url:
        return await m.reply_text("ɢɪᴠᴇ ᴍᴇ ᴀ ʏᴛ ᴜʀʟ")
    
    if not re.search(r"(?:youtube\.com|youtu\.be)", url):
        return await m.reply_text("ɪɴᴠᴀʟɪᴅ ʏᴏᴜᴛᴜʙᴇ ʟɪɴᴋ")
    
    try:
        await m.delete()
        if m.reply_to_message:
            await m.reply_to_message.delete()
    except:
        pass
    
    wait = await m.reply_text("ᴘʀᴏᴄᴇssɪɴɢ...")
    
    # Extract video IDs from URL
    video_ids = extract_video_ids(url)
    if not video_ids:
        return await wait.edit_text("ᴇʀʀᴏʀ ᴇxᴛʀᴀᴄᴛɪɴɢ ᴠɪᴅᴇᴏ ɪɴғᴏ")
    
    # Determine range of videos to process
    start_idx = 0
    end_idx = len(video_ids)
    
    if args:
        if len(args) == 1:
            # Only end index provided (/t 5)
            try:
                end_idx = min(int(args[0]), len(video_ids))
            except:
                pass
        elif len(args) >= 2:
            # Both start and end provided (/t 3 7)
            try:
                start_idx = max(0, int(args[0]) - 1)
                end_idx = min(int(args[1]), len(video_ids))
            except:
                pass
    
    # Process the requested videos
    success_count = 0
    for i in range(start_idx, end_idx):
        video_id = video_ids[i]
        status = await process_and_send_thumb(m, video_id, i)
        if status:
            success_count += 1
        await asyncio.sleep(0.5)  # Small delay to avoid rate limiting
    
    await wait.edit_text(f"✅ sᴜᴄᴄᴇssғᴜʟʟʏ sᴇɴᴛ {success_count} ᴛʜᴜᴍʙɴᴀɪʟs")
