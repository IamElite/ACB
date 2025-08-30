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
        print(f"Error: Background image '{background_path}' nahi mili.")
        return
    except Exception as e:
        print(f"Image open karne me error: {e}")
        return

    # === Load Montserrat-Bold for SEASON & HINDI ===
    montserrat_paths = [
        "fonts/Montserrat-Bold.ttf",
        "/app/fonts/Montserrat-Bold.ttf",
    ]
    font_main = None
    for path in montserrat_paths:
        try:
            font_main = ImageFont.truetype(path, size=int(height / 18))
            print(f"Montserrat loaded from: {path}")
            break
        except IOError:
            continue

    if font_main is None:
        print("Montserrat font nahi mili, default use ho raha hai.")
        font_main = ImageFont.load_default()

    # === Load Impact font for EPISODE ===
    impact_paths = [
        "fonts/impact.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
        "/usr/local/share/fonts/Impact.ttf",
        "/usr/share/fonts/truetype/Impact.ttf",
        "/app/fonts/impact.ttf"
    ]
    font_episode = None
    for path in impact_paths:
        try:
            font_episode = ImageFont.truetype(path, size=int(height / 9))
            print(f"Impact font loaded from: {path}")
            break
        except IOError:
            continue

    if font_episode is None:
        print("IMPACT font nahi mili, default use ho raha hai.")
        font_episode = ImageFont.load_default()

    # === Top Left: SEASON XX ===
    margin = int(width * 0.03)
    season_text = f"SEASON {season}"
    draw.text((margin, margin), season_text, fill="white", font=font_main, stroke_width=2, stroke_fill="black")

    # === Top Right: Diagonal Black Ribbon + "HINDI" ===
    lang_text = lang.upper()

    # Draw black diagonal ribbon (top-right corner)
    ribbon_size = int(width * 0.4)
    draw.polygon([
        (width, 0),
        (width, int(ribbon_size * 0.6)),
        (width - int(ribbon_size * 0.6), 0)
    ], fill='black')

    # Get text size
    try:
        bbox = font_main.getbbox(lang_text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        text_width, text_height = font_main.getsize(lang_text)

    # Create transparent image for text
    text_img = Image.new('RGBA', (text_width + 10, text_height + 10), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((5, 5), lang_text, font=font_main, fill="white")

    # Rotate 45 degrees
    rotated_text = text_img.rotate(45, expand=True, resample=Image.BICUBIC)

    # Position: top-right, over ribbon
    rt_w, rt_h = rotated_text.size
    paste_x = width - rt_w - int(width * 0.08)
    paste_y = int(height * 0.015)

    # Paste onto main image
    image.paste(rotated_text, (paste_x, paste_y), rotated_text)

    # === Bottom Right: EPISODE XX (Golden with Black Stroke) ===
    episode_text = f"EPISODE {episode}"

    try:
        epi_bbox = font_episode.getbbox(episode_text)
        epi_width = epi_bbox[2] - epi_bbox[0]
        epi_height = epi_bbox[3] - epi_bbox[1]
    except:
        epi_width, epi_height = font_episode.getsize(episode_text)

    x = width - epi_width - margin
    y = height - epi_height - int(margin * 1.5)

    # Shadow offset
    shadow = int(height * 0.009)

    # Draw black shadow (8 directions)
    for dx in [-shadow, 0, shadow]:
        for dy in [-shadow, 0, shadow]:
            if dx != 0 or dy != 0:
                draw.text((x + dx, y + dy), episode_text, font=font_episode, fill="black")

    # Draw main golden text
    draw.text((x, y), episode_text, font=font_episode, fill="#FFC300")

    # Save final image
    try:
        image.save(output_path, "PNG")
        print(f"Thumbnail successfully saved: '{output_path}'")
    except Exception as e:
        print(f"Image save karne me error: {e}")


# === Command Handler ===
@app.on_message(filters.command("gt"))
async def generate_thumbnail_handler(client: Client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("❌ Kripya ek photo (caption ke sath) ko reply karke yeh command use karein.")
        return

    replied_msg = message.reply_to_message

    if not replied_msg.photo:
        await message.reply_text("❌ Sirf photo par hi /gt command kaam karega.")
        return

    if not replied_msg.caption:
        await message.reply_text(
            "❌ Caption missing! Kripya caption me ye format daalein:\n"
            "`SEASON EPISODE LANGUAGE`\n\n"
            "📌 Example: `14 322 HINDI`"
        )
        return

    try:
        parts = replied_msg.caption.strip().split()
        if len(parts) < 2:
            await message.reply_text("❌ Caption galat hai! Format: `SEASON EPISODE [LANGUAGE]`")
            return

        season = parts[0].strip()
        episode = parts[1].strip()
        lang = parts[2].strip().upper() if len(parts) >= 3 else "HINDI"

    except Exception as e:
        await message.reply_text(f"❌ Caption parse karne me error: {e}")
        return

    processing_msg = await message.reply_text("`🖼️ Thumbnail ban raha hai, कृपया प्रतीक्षा करें...`")

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
                caption=f"✅ **Thumbnail Taiyar!**\n\n"
                        f"🎬 **Season:** {season}\n"
                        f"🔢 **Episode:** {episode}\n"
                        f"🌐 **Language:** {lang}"
            )
            await processing_msg.delete()
        else:
            await message.reply_text("❌ Thumbnail generate toh hua, lekin save nahi hua.")

    except Exception as e:
        await processing_msg.edit_text(f"❌ Thumbnail banane me error aaya:\n`{e}`")
    
    finally:
        # Cleanup
        if os.path.exists(download_path):
            os.remove(download_path)
        if os.path.exists(output_path):
            os.remove(output_path)
