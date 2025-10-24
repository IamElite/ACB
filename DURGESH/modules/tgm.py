import os
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode
from DURGESH import app
import requests

def upload_to_catbox(file_path):
    """Upload to catbox.moe with retry logic"""
    url = "https://catbox.moe/user/api.php"
    data = {"reqtype": "fileupload", "json": "true"}
    
    try:
        with open(file_path, "rb") as f:
            files = {"fileToUpload": f}
            response = requests.post(url, data=data, files=files, timeout=60)
        
        if response.status_code == 200:
            return True, response.text.strip()
        else:
            return False, f"Catbox error: {response.status_code}"
    except requests.exceptions.Timeout:
        return False, "Catbox timeout - trying alternative..."
    except Exception as e:
        return False, str(e)

def upload_to_telegraph(file_path):
    """Fallback: Upload to Telegraph"""
    try:
        from telegraph import Telegraph
        telegraph = Telegraph()
        telegraph.create_account(short_name='Bot')
        
        with open(file_path, 'rb') as f:
            response = telegraph.upload_file(f)
        
        if response:
            return True, f"https://telegra.ph{response[0]['src']}"
        return False, "Telegraph upload failed"
    except Exception as e:
        return False, f"Telegraph error: {str(e)}"

def upload_to_tmpfiles(file_path):
    """Another fallback: tmpfiles.org"""
    try:
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post('https://tmpfiles.org/api/v1/upload', files=files, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            download_url = data.get('data', {}).get('url', '')
            if download_url:
                return True, download_url
        return False, "Tmpfiles upload failed"
    except Exception as e:
        return False, str(e)

@app.on_message(filters.command(["tgm", "tgt", "telegraph", "tl"]))
async def get_link_group(client, message):
    if not message.reply_to_message:
        return await message.reply_text(
            "Pʟᴇᴀsᴇ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴍᴇᴅɪᴀ ᴛᴏ ᴜᴘʟᴏᴀᴅ"
        )
    
    media = message.reply_to_message
    file_size = 0
    
    if media.photo:
        file_size = media.photo.file_size
    elif media.video:
        file_size = media.video.file_size
    elif media.document:
        file_size = media.document.file_size
    else:
        return await message.reply_text("ᴍᴇᴅɪᴀ ᴛʏᴘᴇ sᴜᴘᴘᴏʀᴛᴇᴅ ɴᴀʜɪ ʜᴀɪ")
    
    if file_size > 200 * 1024 * 1024:
        return await message.reply_text("Fɪʟᴇ 200MB sᴇ ᴢʏᴀᴅᴀ ʜᴏɴᴀ ɴᴀʜɪ ᴄʜᴀʜɪᴇ")
    
    local_path = None
    try:
        text = await message.reply("Pʀᴏᴄᴇssɪɴɢ... ⏳")
        
        async def progress(current, total):
            try:
                percent = (current * 100) / total
                await text.edit_text(f"📥 Dᴏᴡɴʟᴏᴀᴅɪɴɢ... {percent:.1f}%")
            except Exception:
                pass
        
        local_path = await media.download(progress=progress)
        await text.edit_text("📤 Uᴘʟᴏᴀᴅɪɴɢ...")
        
        # Try catbox first
        success, result = upload_to_catbox(local_path)
        
        # If catbox fails, try tmpfiles
        if not success:
            await text.edit_text("🔄 Cᴀᴛʙᴏx sᴇ ɪssᴜᴇ... Tᴍᴘғɪʟᴇs ᴛʀʏ ᴄᴀʀ ʀʜᴇ")
            success, result = upload_to_tmpfiles(local_path)
        
        # If tmpfiles fails, try telegraph
        if not success:
            await text.edit_text("🔄 Aʟᴛᴇʀɴᴀᴛɪᴠ sᴇʀᴠᴇʀ ᴛʀʏ ᴄᴀʀ ʀʜᴇ...")
            success, result = upload_to_telegraph(local_path)
        
        if success:
            await text.edit_text(
                f"✅ **Upload Successful!**\n\n[👉 ʟɪɴᴋ ᴛᴀᴘ ᴋᴀʀ 👈]({result})",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "🔗 ᴏᴘᴇɴ ʟɪɴᴋ",
                                url=result,
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "👨‍💻 ᴄʀᴇᴀᴛᴇᴅ ʙʏ",
                                url="https://t.me/yourusername",
                            )
                        ]
                    ]
                ),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await text.edit_text(
                f"❌ Sᴀʙ sᴇʀᴠᴇʀ ғᴀɪʟ ʜᴏ ɢᴀʏᴀ\n\n**Rᴇᴀsᴏɴ:** {result}"
            )
    
    except Exception as e:
        await message.reply_text(
            f"❌ **Eʀʀᴏʀ**\n\n`{str(e)}`",
            parse_mode=ParseMode.MARKDOWN
        )
    
    finally:
        if local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except Exception:
                pass
