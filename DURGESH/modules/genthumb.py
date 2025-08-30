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
    except Exception as e:
        print(f"Error opening image: {e}")
        return

    # === Load Fonts ===
    font_paths = [
        "fonts/Impact.ttf",   # Impact is bold style for episode text
        "fonts/Montserrat-Bold.ttf",
        "/app/fonts/Montserrat-Bold.ttf",
    ]
    font_episode = None
    font_season = None
    font_lang = None

    for path in font_paths:
        try:
            font_episode = ImageFont.truetype(path, size=int(height / 6))   # bada for EPISODE
            font_season = ImageFont.truetype(path, size=int(height / 18))   # chhota for SEASON
            font_lang = ImageFont.truetype(path, size=int(height / 22))     # ribbon ke liye
            break
        except IOError:
            continue

    if font_episode is None:
        font_episode = ImageFont.load_default()
        font_season = ImageFont.load_default()
        font_lang = ImageFont.load_default()

    # === Top Left: SEASON XX ===
    margin = int(width * 0.02)
    season_text = f"SEASON {season}"
    draw.text(
        (margin, margin),
        season_text,
        fill="white",
        font=font_season,
        stroke_width=2,
        stroke_fill="black"
    )

    # === Top Right: White Ribbon + HINDI ===
    ribbon_height = int(height * 0.12)
    ribbon_width = int(width * 0.35)
    ribbon_points = [(width, 0), (width - ribbon_width, 0), (width, ribbon_height)]
    draw.polygon(ribbon_points, fill="white")

    lang_text = lang.upper()
    text_w, text_h = draw.textsize(lang_text, font=font_lang)
    lang_x = width - ribbon_width + 20
    lang_y = 10
    draw.text(
        (lang_x, lang_y),
        lang_text,
        font=font_lang,
        fill="black"
    )

    # === Bottom Center: EPISODE XXX ===
    episode_text = f"EPISODE {episode}"
    epi_w, epi_h = draw.textsize(episode_text, font=font_episode)
    epi_x = (width - epi_w) // 2
    epi_y = height - epi_h - int(height * 0.05)

    draw.text(
        (epi_x, epi_y),
        episode_text,
        font=font_episode,
        fill="#FFD700",  # Golden yellow
        stroke_width=6,
        stroke_fill="black"
    )

    # Save
    try:
        image.save(output_path, "PNG")
        print(f"Thumbnail saved: {output_path}")
    except Exception as e:
        print(f"Save error: {e}")


# === Command Handler ===
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
            "**Example:** `11 306 HINDI`"
        )
        return

    try:
        parts = replied_msg.caption.strip().split()
        if len(parts) < 2:
            await message.reply_text("Caption galat hai! Format: `SEASON EPISODE [LANGUAGE]`")
            return

        season = parts[0].strip()
        episode = parts[1].strip()
        lang = parts[2].strip().upper() if len(parts) >= 3 else "HINDI"

    except Exception as e:
        await message.reply_text(f"Caption parse karne me error: {e}")
        return

    processing_msg = await message.reply_text("`Thumbnail ban raha hai...`")

    download_path = await replied_msg.download(file_name=f"bg_{message.id}.jpg")
    output_path = f"thumb_{message.id}.png"

    try:
        create_thumbnail(
            background_path=download_path,
            season=season,
            episode=episode,
            lang=lang,
            output_path=output_path
        )

        if os.path.exists(output_path):
            await message.reply_photo(
                photo=output_path,
                caption=f"✅ Thumbnail Taiyar!\n\n**Season:** {season}\n**Episode:** {episode}\n**Language:** {lang}"
            )
            await processing_msg.delete()
        else:
            await message.reply_text("❌ Thumbnail save nahi hua.")

    except Exception as e:
        await processing_msg.edit_text(f"❌ Error: `{e}`")
    
    finally:
        if os.path.exists(download_path):
            os.remove(download_path)
        if os.path.exists(output_path):
            os.remove(output_path)

