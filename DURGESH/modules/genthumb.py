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
    montserrat_paths = [
        "fonts/Montserrat-Bold.ttf",
        "/app/fonts/Montserrat-Bold.ttf",
    ]
    font_main = None
    for path in montserrat_paths:
        try:
            font_main = ImageFont.truetype(path, size=int(height / 25))
            break
        except IOError:
            continue
    if font_main is None:
        font_main = ImageFont.load_default()

    # === Top Left: SEASON XX ===
    margin = int(width * 0.02)
    season_text = f"SEASON {season}"
    draw.text((margin, margin), season_text, fill="white", font=font_main, stroke_width=1, stroke_fill="black")

    # === Top Right: Black Diagonal Triangle + HINDI ===
    # Draw black diagonal triangle (from top-right to bottom-left)
    triangle_points = [
        (width, 0),
        (width, int(height * 0.2)),
        (int(width * 0.7), 0)
    ]
    draw.polygon(triangle_points, fill='black')

    # Add "HINDI" inside triangle (white, small)
    lang_text = lang.upper()
    try:
        bbox = font_main.getbbox(lang_text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except:
        text_width, text_height = font_main.getsize(lang_text)

    # Position: center of triangle
    x = width - int(text_width * 1.2)
    y = int(text_height * 0.8)
    draw.text((x, y), lang_text, fill="white", font=font_main)

    # === Bottom Right: EPISODE XXX ===
    episode_text = f"EPISODE {episode}"
    try:
        epi_bbox = font_main.getbbox(episode_text)
        epi_width = epi_bbox[2] - epi_bbox[0]
        epi_height = epi_bbox[3] - epi_bbox[1]
    except:
        epi_width, epi_height = font_main.getsize(episode_text)

    x = width - epi_width - margin
    y = height - epi_height - margin

    # Yellow text (no shadow)
    draw.text((x, y), episode_text, fill="#FFD700", font=font_main)

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
