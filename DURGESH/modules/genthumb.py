# plugins/gt.py  (or wherever you keep handlers)

import os
from pyrogram import Client, filters
from pyrogram.types import Message
from PIL import Image, ImageDraw, ImageFont
from DURGESH import app

def create_thumbnail(background_path, season, episode, lang, output_path="thumbnail.png"):
    try:
        image = Image.open(background_path).convert("RGBA")
        width, height = image.size
        draw = ImageDraw.Draw(image)
    except FileNotFoundError:
        print(f"Error: Background image '{background_path}' nahi mili. Path check karein.")
        return

    try:
        font_main = ImageFont.truetype("fonts/Montserrat-Bold.ttf", size=int(height / 18))
        font_episode = ImageFont.truetype("fonts/Montserrat-SemiBold.ttf", size=int(height / 9))
    except IOError:
        print("Font files (Montserrat-Bold.ttf, Montserrat-SemiBold.ttf) fonts/ folder me nahi mili.")
        font_main = ImageFont.load_default()
        font_episode = ImageFont.load_default()

    margin = int(width * 0.03)
    season_text = f"SEASON {season}"
    draw.text((margin, margin), season_text, fill="white", font=font_main, stroke_width=2, stroke_fill="black")

    ribbon_size = int(width * 0.35)
    draw.polygon([(width - ribbon_size, 0), (width, 0), (width, ribbon_size)], fill='black')

    lang_text = lang.upper()
    
    try:
        lang_bbox = font_main.getbbox(lang_text)
        lang_text_width = lang_bbox[2]
        lang_text_height = lang_bbox[3]
    except AttributeError:
        lang_text_width, lang_text_height = font_main.getsize(lang_text)
        
    text_image = Image.new('RGBA', (lang_text_width, lang_text_height), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_image)
    text_draw.text((0, 0), lang_text, font=font_main, fill='white')

    rotated_text_image = text_image.rotate(45, expand=1, resample=Image.BICUBIC)

    rt_width, rt_height = rotated_text_image.size
    paste_pos_x = width - int(rt_width * 0.75)
    paste_pos_y = int(rt_height * 0.1)
    
    image.paste(rotated_text_image, (paste_pos_x, paste_pos_y), rotated_text_image)
    
    episode_text = f"EPISODE {episode}"
    
    try:
        epi_bbox = font_episode.getbbox(episode_text)
        epi_text_width = epi_bbox[2]
        epi_text_height = epi_bbox[3]
    except AttributeError:
        epi_text_width, epi_text_height = font_episode.getsize(episode_text)

    x = width - epi_text_width - margin
    y = height - epi_text_height - margin

    shadow_offset = int(height * 0.008)
    shadow_color = "black"
    draw.text((x + shadow_offset, y + shadow_offset), episode_text, font=font_episode, fill=shadow_color)

    main_color = "#FFC300"
    draw.text((x, y), episode_text, font=font_episode, fill=main_color)

    image.save(output_path, "PNG")
    print(f"Thumbnail successfully ban gaya hai: '{output_path}'")


@app.on_message(filters.command("gt"))
async def generate_thumbnail_handler(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("Kripya ek photo (caption ke sath) ko reply karke yeh command use karein.")
        return

    replied_msg = message.reply_to_message

    if not replied_msg.photo:
        await message.reply_text("Aap sirf photo par hi reply kar sakte hain.")
        return

    if not replied_msg.caption:
        await message.reply_text(
            "Is photo me caption nahi hai! Kripya caption me details daalein.\n"
            "**Format:** `SEASON EPISODE LANGUAGE`\n\n"
            "**Example:** `14 322 HINDI`"
        )
        return

    try:
        parts = replied_msg.caption.split()
        
        if len(parts) < 2 or len(parts) > 3:
            await message.reply_text(
                "Caption ka format galat hai!\n"
                "**Sahi format:** `SEASON EPISODE LANGUAGE`\n\n"
                "**Example:** `14 322 HINDI` (Language optional hai)."
            )
            return

        season = parts[0]
        episode = parts[1]
        lang = parts[2].upper() if len(parts) == 3 else "HINDI"

    except Exception as e:
        await message.reply_text(f"Caption ko process karne me error aaya: {e}")
        return

    processing_msg = await message.reply_text("`Thumbnail ban raha hai, कृपया प्रतीक्षा करें...`")

    download_path = await replied_msg.download(file_name=f"background_{message.id}.jpg")
    output_path = f"final_{message.id}.png"

    try:
        create_thumbnail(
            background_path=download_path,
            season=season,
            episode=episode,
            lang=lang,
            output_path=output_path
        )
        
        await message.reply_photo(
            photo=output_path,
            caption=f"✅ Thumbnail Taiyar!\n\n**Season:** {season}\n**Episode:** {episode}\n**Language:** {lang}"
        )
        
        await processing_msg.delete()

    except Exception as e:
        await processing_msg.edit_text(f"❌ Thumbnail banane me error aaya:\n`{e}`")
    
    finally:
        if os.path.exists(download_path):
            os.remove(download_path)
        if os.path.exists(output_path):
            os.remove(output_path)


