import re, subprocess, os, asyncio, urllib.request, requests
from pyrogram import Client, filters
from DURGESH import app
from config import ADMINS
import yt_dlp
from urllib.parse import urlparse, parse_qs

def extract_video_ids(url):
    """Extract video IDs from a YouTube URL (single video or playlist)"""
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_json': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:  # This is a playlist
                return [entry['id'] for entry in info['entries'] if entry]
            else:  # This is a single video
                return [info['id']]
                
    except Exception as e:
        print(f"Error extracting video IDs: {e}")
        # Fallback: try to extract ID manually
        return manual_extract_video_ids(url)

def manual_extract_video_ids(url):
    """Manually extract video IDs from YouTube URLs as fallback"""
    video_ids = []
    
    # Check if it's a playlist
    if "list=" in url:
        try:
            # Try to get videos from playlist
            ydl_opts = {
                'quiet': True,
                'extract_flat': True,
                'playlist_items': '1-10',  # Limit to first 10 videos
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    return [entry['id'] for entry in info['entries'] if entry]
        except:
            pass
    
    # Try to extract single video ID
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtube\.com\/embed\/)([0-9A-Za-z_-]{11})',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            video_ids.append(match.group(1))
            break
    
    return video_ids if video_ids else None

def get_best_thumb(video_id):
    """Get the best available thumbnail for a YouTube video ID"""
    # Try different quality levels in order
    qualities = [
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",  # Highest quality
        f"https://i.ytimg.com/vi/{video_id}/sddefault.jpg",      # Standard definition
        f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",      # High quality
        f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",      # Medium quality
        f"https://i.ytimg.com/vi/{video_id}/default.jpg",        # Default quality
    ]
    
    # Check which quality is available
    for quality_url in qualities:
        try:
            # Try to open the URL to see if it exists
            req = urllib.request.Request(
                quality_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return quality_url
        except:
            continue
    
    # If none of the specific thumbnails work, return the default one
    return f"https://i.ytimg.com/vi/{video_id}/default.jpg"

def is_valid_youtube_url(url):
    """Check if the URL is a valid YouTube URL"""
    youtube_patterns = [
        r'^https?://(www\.)?youtube\.com/',
        r'^https?://youtu\.be/',
        r'^https?://(www\.)?youtube\.com/shorts/',
        r'^https?://(www\.)?youtube\.com/embed/',
        r'^https?://(www\.)?youtube\.com/watch\?v=',
        r'^https?://(www\.)?youtube\.com/playlist\?list='
    ]
    
    return any(re.match(pattern, url) for pattern in youtube_patterns)

async def download_thumbnail(thumb_url):
    """Download thumbnail with proper error handling"""
    try:
        req = urllib.request.Request(
            thumb_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                return response.read()
        return None
    except Exception as e:
        print(f"Error downloading thumbnail: {e}")
        return None

async def process_and_send_thumb(m, video_id, index=None):
    """Process a single thumbnail and send it"""
    thumb_url = get_best_thumb(video_id)
    
    try:
        # Download the thumbnail
        img_data = await download_thumbnail(thumb_url)
        if not img_data:
            # Try to send direct URL if download fails
            caption = f"Video {index+1}" if index is not None else None
            await m.reply_photo(thumb_url, caption=caption)
            return True
            
        infile, outfile = f"in_{video_id}.jpg", f"out_{video_id}.jpg"
        
        # Save the downloaded image
        with open(infile, "wb") as f:
            f.write(img_data)
        
        # Try to process with ImageMagick if available
        processed = False
        try:
            # Check if ImageMagick is available
            subprocess.run(["convert", "-version"], capture_output=True, check=True)
            
            # Process the image
            result = subprocess.run([
                "convert", infile,
                "-modulate", "100,115",
                "-sigmoidal-contrast", "4x50%",
                "-enhance",
                "-contrast-stretch", "0.5%x0.5%",
                outfile
            ], capture_output=True, timeout=30)
            
            if result.returncode == 0 and os.path.exists(outfile):
                with open(outfile, "rb") as f:
                    caption = f"Video {index+1}" if index is not None else None
                    await m.reply_photo(f, caption=caption)
                processed = True
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            # ImageMagick not available or processing failed
            pass
        
        # If processing failed, send the original image
        if not processed:
            with open(infile, "rb") as f:
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
            # Final fallback: send direct URL
            caption = f"Video {index+1}" if index is not None else None
            await m.reply_photo(thumb_url, caption=caption)
            return True
        except Exception as e2:
            print(f"Even direct URL failed: {e2}")
            return False

@app.on_message(filters.command(["thumbnail","thumb","t"], prefixes=["/","!",".", ""]) & filters.user(ADMINS))
async def send_thumb(_, m):
    # Extract URL from message or reply
    if m.reply_to_message and m.reply_to_message.text:
        # Extract URL from replied message text
        text = m.reply_to_message.text.strip()
        # Find YouTube URL in the text
        url_match = re.search(r'(https?://[^\s]+)', text)
        if url_match:
            url = url_match.group(1)
            # Extract arguments from command
            args = m.text.split()[1:] if len(m.text.split()) > 1 else []
        else:
            return await m.reply_text("ɴᴏ ʏᴏᴜᴛᴜʙᴇ ʟɪɴᴋ ғᴏᴜɴᴅ ɪɴ ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ")
    else:
        # Extract URL and arguments from command
        parts = m.text.split()
        url = None
        args = []
        
        # Find the URL in the message parts
        for part in parts[1:]:
            if is_valid_youtube_url(part):
                url = part
                break
        
        # Collect arguments (skip the URL)
        for part in parts[1:]:
            if part != url:
                args.append(part)
    
    if not url:
        return await m.reply_text("ɢɪᴠᴇ ᴍᴇ ᴀ ᴠᴀʟɪᴅ ʏᴏᴜᴛᴜʙᴇ ᴜʀʟ")
    
    if not is_valid_youtube_url(url):
        return await m.reply_text("ɪɴᴠᴀʟɪᴅ ʏᴏᴜᴛᴜʙᴇ ʟɪɴᴋ")
    
    try:
        await m.delete()
    except:
        pass
        
    try:
        if m.reply_to_message:
            await m.reply_to_message.delete()
    except:
        pass
    
    wait = await m.reply_text("ᴘʀᴏᴄᴇssɪɴɢ...")
    
    # Extract video IDs from URL
    video_ids = extract_video_ids(url)
    if not video_ids:
        return await wait.edit_text("ᴇʀʀᴏʀ ᴇxᴛʀᴀᴄᴛɪɴɢ ᴠɪᴅᴇᴏ ɪɴғᴏ. ᴍᴀᴋᴇ sᴜʀᴇ ᴛʜᴇ ᴜʀʟ ɪs ᴠᴀʟɪᴅ.")
    
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
    
    # Limit the number of thumbnails to process at once
    max_thumbnails = 10  # Reduced from 20 to 10 for better reliability
    if end_idx - start_idx > max_thumbnails:
        end_idx = start_idx + max_thumbnails
        await wait.edit_text(f"ʟɪᴍɪᴛɪɴɢ ᴛᴏ {max_thumbnails} ᴛʜᴜᴍʙɴᴀɪʟs. ᴜsᴇ sᴘᴇᴄɪғɪᴄ ʀᴀɴɢᴇ ғᴏʀ ᴍᴏʀᴇ.")
        await asyncio.sleep(2)
    
    # Process the requested videos
    success_count = 0
    for i in range(start_idx, end_idx):
        video_id = video_ids[i]
        status = await process_and_send_thumb(m, video_id, i)
        if status:
            success_count += 1
        await asyncio.sleep(1)  # Delay to avoid rate limiting
    
    if success_count > 0:
        await wait.edit_text(f"✅ sᴜᴄᴄᴇssғᴜʟʟʏ sᴇɴᴛ {success_count} ᴛʜᴜᴍʙɴᴀɪʟs")
    else:
        await wait.edit_text("❌ ғᴀɪʟᴇᴅ ᴛᴏ sᴇɴᴅ ᴀɴʏ ᴛʜᴜᴍʙɴᴀɪʟs. ᴄʜᴇᴄᴋ ʟᴏɢs ғᴏʀ ᴇʀʀᴏʀs.")

# Add a help command
@app.on_message(filters.command(["thelp", "thumbhelp"], prefixes=["/","!",".", ""]) & filters.user(ADMINS))
async def thumb_help(_, m):
    help_text = """
**📸 YouTube Thumbnail Bot Help**

**Commands:**
- `/t [url]` - Get thumbnails from URL
- `/t [range] [url]` - Get specific range of thumbnails
- `/t [start] [end] [url]` - Get thumbnails from start to end
- Reply to a message with `/t` - Get thumbnails from replied message

**Examples:**
- `/t https://youtube.com/playlist?list=...` - All thumbnails
- `/t 5 https://youtube.com/playlist?list=...` - First 5 thumbnails
- `/t 3 7 https://youtube.com/playlist?list=...` - Thumbnails 3 to 7

**Note:** Limited to 10 thumbnails at once for better reliability.
    """
    await m.reply_text(help_text)

# Test command to check if everything is working
@app.on_message(filters.command(["ttest"], prefixes=["/","!",".", ""]) & filters.user(ADMINS))
async def test_thumb(_, m):
    """Test command to verify the bot is working"""
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Famous test video
    
    wait = await m.reply_text("🧪 ᴛᴇsᴛɪɴɢ ᴛʜᴜᴍʙɴᴀɪʟ ᴇxᴛʀᴀᴄᴛɪᴏɴ...")
    
    # Test URL validation
    if not is_valid_youtube_url(test_url):
        return await wait.edit_text("❌ URL validation failed")
    
    # Test video ID extraction
    video_ids = extract_video_ids(test_url)
    if not video_ids:
        return await wait.edit_text("❌ Video ID extraction failed")
    
    # Test thumbnail retrieval
    thumb_url = get_best_thumb(video_ids[0])
    if not thumb_url:
        return await wait.edit_text("❌ Thumbnail URL generation failed")
    
    # Test thumbnail download
    img_data = await download_thumbnail(thumb_url)
    if not img_data:
        return await wait.edit_text("❌ Thumbnail download failed")
    
    # Test sending thumbnail
    try:
        with open("test_thumb.jpg", "wb") as f:
            f.write(img_data)
        with open("test_thumb.jpg", "rb") as f:
            await m.reply_photo(f, caption="✅ Test successful!")
        os.remove("test_thumb.jpg")
        await wait.edit_text("✅ All tests passed! Bot is working correctly.")
    except Exception as e:
        await wait.edit_text(f"❌ Failed to send test thumbnail: {e}")
