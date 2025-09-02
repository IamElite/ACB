import os
import json
import re
import html
from DURGESH import app
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import MessageMediaType, ParseMode

# Captions store karne ke liye JSON file
CAPTIONS_FILE = 'captions.json'

# JSON se data load/save karne ke functions
def load_captions():
    if os.path.exists(CAPTIONS_FILE):
        with open(CAPTIONS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_captions(captions_data):
    with open(CAPTIONS_FILE, 'w') as f:
        json.dump(captions_data, f, indent=4)

# Aapke diye gaye extraction functions
def extract_episode(fname: str) -> str:
    match0 = re.search(r'EPS(\d+)\s*EP(\d+)\s*\((\d+)\)', fname, re.IGNORECASE)
    if match0:
        ep2 = match0.group(2)
        ep3 = match0.group(3)
        return f"{ep2} ({ep3})"
    match1 = re.search(r'S(\d+)\s*(?:E|EP)(\d+)\s*\((\d+)\)', fname, re.IGNORECASE)
    if match1:
        seasonal_ep = match1.group(2).zfill(2)
        overall_ep = match1.group(3)
        return f"{seasonal_ep} ({overall_ep})"
    match2 = re.search(r'S(\d+)\s*(?:E|EP)(\d+)', fname, re.IGNORECASE)
    if match2:
        episode = match2.group(2).zfill(2)
        return episode
    match3 = re.search(r'(?:E|EP)\s*\((\d+)\)', fname, re.IGNORECASE)
    if match3:
        overall_ep = match3.group(1)
        return f"({overall_ep})"
        
    match4 = re.search(r'-\s*(\d+)', fname, re.IGNORECASE)
    if match4:
        episode = match4.group(1).zfill(2)
        return f"{episode}"
    return "N/A"

def extract_season(fname: str) -> str:
    s_pats = [
        r'S(\d+)(?:E|EP)(\d+)',
        r'S(\d+)\s*(?:E|EP|-\s*EP)(\d+)',
        r'S(\d+)[^\d]*(\d+)',
        r'\bseason\s*(\d+)\b',
        r'\bs(\d+)\b'
    ]
    for pat in s_pats:
        m = re.search(pat, fname, re.IGNORECASE)
        if m:
            return m.group(1)
    return "N/A"

def extract_quality(text: str) -> str:
    qpats = [
        (r'[([{<]?\s*4k\s*[)\]}>]?', lambda m: "4k"),
        (r'[([{<]?\s*2k\s*[)\]}>]?', lambda m: "2k"),
        (r'[([{<]?\s*4kX264\s*[)\]}>]?', lambda m: "4kX24"),
        (r'[([{<]?\s*4kx265\s*[)\]}>]?', lambda m: "4kx265"),
        (r'\bWEB[.\- ]*DL\b', lambda m: "WEB-DL"),
        (r'[([{<]?\s*HdRip\s*[)\]}>]?|\bHdRip\b', lambda m: "HdRip"),
        (r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', lambda m: m.group(1) or m.group(2)),
    ]
    for pat, func in qpats:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return func(m)
    return "Unknown"

# File size ko readable format mein convert karne ka function
def get_readable_file_size(size_in_bytes):
    if size_in_bytes is None:
        return "0 B"
    SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    index = 0
    while size_in_bytes >= 1024 and index < len(SIZE_UNITS) - 1:
        size_in_bytes /= 1024
        index += 1
    return f"{size_in_bytes:.2f} {SIZE_UNITS[index]}"

# Duration ko format karne ka function (error fix)
def format_duration(duration):
    if duration is None:
        return "N/A"
    
    try:
        # Float ko integer mein convert karna
        total_seconds = int(duration)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except (ValueError, TypeError):
        return "N/A"

# /setcaption command handler
@app.on_message(filters.command("setcaption") & filters.group)
async def set_caption(client, message: Message):
    chat_id = str(message.chat.id)
    
    # Check if caption is provided
    if len(message.text.split()) < 2:
        await message.reply_text("❌ Please provide a caption after the command.\nExample: `/setcaption Your HTML Caption Here`")
        return
    
    # Puri caption text extract karna (HTML tags ke saath)
    user_caption = message.text.split("/setcaption", 1)[1].strip()
    
    captions_data = load_captions()
    captions_data[chat_id] = user_caption
    save_captions(captions_data)
    
    await message.reply_text("✅ Caption successfully set!\nAb se yahan upload ki gayi media ka yehi caption hoga.")

# Media messages ko handle karna (photos, videos, documents)
@app.on_message(filters.media & filters.group)
async def handle_media(client, message: Message):
    chat_id = str(message.chat.id)
    captions_data = load_captions()
    
    # Agar caption set nahi hai to kuch nahi karna
    if chat_id not in captions_data:
        return
    
    # File details extract karna
    filename = None
    filesize = None
    duration = None
    
    if message.document:
        filename = message.document.file_name
        filesize = message.document.file_size
    elif message.video:
        filename = message.video.file_name if message.video.file_name else "Video"
        filesize = message.video.file_size
        duration = message.video.duration
    elif message.audio:
        filename = message.audio.file_name if message.audio.file_name else "Audio"
        filesize = message.audio.file_size
        duration = message.audio.duration
    elif message.photo:
        filename = "Photo"
        filesize = None  # Photos usually don't have file_size in Pyrogram
    
    # Agar filename nahi hai to kuch nahi karna
    if not filename:
        return
    
    # Extract metadata from filename
    episode = extract_episode(filename)
    season = extract_season(filename)
    quality = extract_quality(filename)
    
    # File size ko readable format mein convert karna
    readable_size = get_readable_file_size(filesize)
    
    # Duration ko format karna (fixed error)
    readable_duration = format_duration(duration)
    
    # Custom caption ko replace karna (HTML entities escape karna)
    custom_caption = captions_data[chat_id]
    custom_caption = custom_caption.replace("{filename}", html.escape(filename.split('.')[0]))  # Remove extension and escape
    custom_caption = custom_caption.replace("{filesize}", html.escape(readable_size))
    custom_caption = custom_caption.replace("{duration}", html.escape(readable_duration))
    custom_caption = custom_caption.replace("{quality}", html.escape(quality))
    custom_caption = custom_caption.replace("{season}", html.escape(season))
    custom_caption = custom_caption.replace("{episode}", html.escape(episode))
    
    try:
        # Media message ka caption edit karna with HTML parsing
        await message.edit_caption(
            caption=custom_caption,
            parse_mode=ParseMode.HTML
        )
        print(f"Caption updated for message in chat {chat_id}")
    except Exception as e:
        print(f"Error editing caption: {e}")
