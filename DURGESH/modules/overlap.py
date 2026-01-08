import os, asyncio, uuid, tempfile, subprocess, aiohttp
from io import BytesIO
from PIL import Image
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from DURGESH import app

OVERLAP_CACHE = {}

@app.on_message(filters.command(["overlap", "overlay", "ol"], prefixes=["/", "!", ".", ""]))
async def overlap_cmd(client, message):
    if not getattr(message, "command", None) or len(message.command) < 3:
        return await message.reply_text(
            "<b>🖼 Image Overlay Tool</b>\n\n"
            "<b>Usage:</b>\n"
            "<code>/overlap bg_url logo.png [scale%]</code>\n\n"
            "<b>Parameters:</b>\n"
            "• <code>bg_url</code> - Background image URL (any format)\n"
            "• <code>logo.png</code> - Logo/overlay PNG URL\n"
            "• <code>scale%</code> - Optional scale (default: 100)\n\n"
            "<b>Example:</b>\n"
            "<code>/overlap https://img.jpg https://logo.png 50</code>",
            parse_mode=ParseMode.HTML
        )
    
    bg_url = message.command[1]
    png_url = message.command[2]
    scale = 100
    if len(message.command) > 3:
        try:
            scale = int(message.command[3].replace("%", ""))
        except:
            scale = 100
    
    cache_id = str(uuid.uuid4())[:8]
    OVERLAP_CACHE[cache_id] = {
        "bg_url": bg_url,
        "png_url": png_url,
        "scale": scale,
        "ts": asyncio.get_event_loop().time()
    }
    
    keyboard = [
        [
            InlineKeyboardButton("↖️ Top Left", callback_data=f"ovl_{cache_id}_tl"),
            InlineKeyboardButton("🔝 Top", callback_data=f"ovl_{cache_id}_tc"),
            InlineKeyboardButton("↗️ Top Right", callback_data=f"ovl_{cache_id}_tr")
        ],
        [
            InlineKeyboardButton("◀️ Middle Left", callback_data=f"ovl_{cache_id}_ml"),
            InlineKeyboardButton("🎯 Center", callback_data=f"ovl_{cache_id}_mc"),
            InlineKeyboardButton("▶️ Middle Right", callback_data=f"ovl_{cache_id}_mr")
        ],
        [
            InlineKeyboardButton("↙️ Bottom Left", callback_data=f"ovl_{cache_id}_bl"),
            InlineKeyboardButton("🔚 Bottom", callback_data=f"ovl_{cache_id}_bc"),
            InlineKeyboardButton("↘️ Bottom Right", callback_data=f"ovl_{cache_id}_br")
        ]
    ]
    
    await message.reply_text(
        f"<b>Choose overlay position:</b> 📍\n\n"
        f"<b>Background:</b> <code>{bg_url[:50]}...</code>\n"
        f"<b>Logo:</b> <code>{png_url[:50]}...</code>\n"
        f"<b>Scale:</b> {scale}%",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


@app.on_callback_query(filters.regex(r"^ovl_"))
async def overlap_callback(client, callback_query):
    parts = callback_query.data.split("_")
    if len(parts) < 3:
        return await callback_query.answer("Invalid!", show_alert=True)
    
    cache_id = parts[1]
    position = parts[2]
    
    if cache_id not in OVERLAP_CACHE:
        return await callback_query.answer("Session expired!", show_alert=True)
    
    cache = OVERLAP_CACHE[cache_id]
    bg_url = cache["bg_url"]
    png_url = cache["png_url"]
    scale = cache["scale"]
    
    await callback_query.answer("Processing...")
    await callback_query.message.edit_text("<i>⏳ Processing images...</i>", parse_mode=ParseMode.HTML)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(bg_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return await callback_query.message.edit_text("<b>❌ Failed to download background</b>", parse_mode=ParseMode.HTML)
                bg_data = await resp.read()
            
            async with session.get(png_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status != 200:
                    return await callback_query.message.edit_text("<b>❌ Failed to download logo</b>", parse_mode=ParseMode.HTML)
                png_data = await resp.read()
        
        bg_img = Image.open(BytesIO(bg_data)).convert("RGBA")
        logo_img = Image.open(BytesIO(png_data)).convert("RGBA")
        
        bg_w, bg_h = bg_img.size
        logo_w, logo_h = logo_img.size
        
        target_w = int(bg_w * 0.5 * scale / 100)
        ratio = target_w / logo_w
        target_h = int(logo_h * ratio)
        
        new_logo_w = target_w
        new_logo_h = target_h
        logo_img = logo_img.resize((new_logo_w, new_logo_h), Image.LANCZOS)
        
        positions = {
            "tl": (0, 0),
            "tc": ((bg_w - new_logo_w) // 2, 0),
            "tr": (bg_w - new_logo_w, 0),
            "ml": (0, (bg_h - new_logo_h) // 2),
            "mc": ((bg_w - new_logo_w) // 2, (bg_h - new_logo_h) // 2),
            "mr": (bg_w - new_logo_w, (bg_h - new_logo_h) // 2),
            "bl": (0, bg_h - new_logo_h),
            "bc": ((bg_w - new_logo_w) // 2, bg_h - new_logo_h),
            "br": (bg_w - new_logo_w, bg_h - new_logo_h)
        }
        
        pos = positions.get(position, (0, 0))
        
        result_img = bg_img.copy()
        result_img.paste(logo_img, pos, logo_img)
        
        normal_buffer = BytesIO()
        result_rgb = result_img.convert("RGB")
        result_rgb.save(normal_buffer, format="JPEG", quality=95)
        normal_buffer.seek(0)
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp.write(normal_buffer.getvalue())
            tmp_path = tmp.name
        
        enhanced_path = tmp_path.replace(".jpg", "_hd.jpg")
        
        try:
            subprocess.run([
                "convert", tmp_path,
                "-modulate", "100,110,100",
                "-contrast-stretch", "0.1x0.1%",
                "-unsharp", "0x1+0.5+0",
                "-quality", "95",
                enhanced_path
            ], check=True, capture_output=True, timeout=30)
            has_enhanced = True
        except:
            has_enhanced = False
        
        await callback_query.message.edit_text("<i>📤 Sending images...</i>", parse_mode=ParseMode.HTML)
        
        chat_id = callback_query.message.chat.id
        
        with open(tmp_path, "rb") as f:
            await client.send_photo(chat_id, f, caption="<b>🖼 Normal (No Enhancement)</b>", parse_mode=ParseMode.HTML)
        
        if has_enhanced and os.path.exists(enhanced_path):
            with open(enhanced_path, "rb") as f:
                await client.send_photo(chat_id, f, caption="<b>✨ HD Enhanced</b>", parse_mode=ParseMode.HTML)
            os.unlink(enhanced_path)
        
        os.unlink(tmp_path)
        
        await callback_query.message.delete()
        
        if cache_id in OVERLAP_CACHE:
            del OVERLAP_CACHE[cache_id]
            
    except Exception as e:
        await callback_query.message.edit_text(f"<b>❌ Error:</b> {str(e)[:100]}", parse_mode=ParseMode.HTML)
