import os, asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from DURGESH.database import image_generator
from DURGESH import app

@app.on_message(filters.command("gen"))
async def generate_image_handler(client: Client, message: Message):
    """Handles /gen command to generate and send AI-generated images."""
    if len(message.command) < 2:
        await message.reply("ᴇᴋ ᴀᴄʜᴀ ꜱᴀ ᴘʀᴏᴍᴘᴛ ᴅᴏ, ᴊᴀɪꜱᴇ: `/gen ultra realistic cat`")
        return

    # Prompt aur image count extract karo
    prompt_parts = message.command[1:]
    amount = 5  # Default 5 images
    if prompt_parts and prompt_parts[-1].isdigit():
        amount = min(int(prompt_parts.pop()), 5)  # Maximum 5 images allowed
    prompt = " ".join(prompt_parts)

    reply_to = message.reply_to_message or message  # Reply target set karo
    waiting_message = await message.reply(
        "ɪᴍᴀɢᴇ ɢᴇɴᴇʀᴀᴛᴇ ʜᴏ ʀᴀʜɪ ʜᴀɪ... ᴛʜᴏᴅᴀ ᴡᴀɪᴛ ᴋᴀʀᴏ!",
        reply_to_message_id=reply_to.id
    )

    try:
        img_urls = await image_generator.generate_images(prompt, amount=amount)
        if not img_urls:
            await message.reply("ᴋᴏɪ ɪᴍᴀɢᴇ ɴᴀʜɪ ᴍɪʟɪ, ᴅᴜʙᴀʀᴀ ᴛʀʏ ᴋᴀʀᴏ!", reply_to_message_id=reply_to.id)
            await waiting_message.delete()
            return

        saved_files = await image_generator.download_images(img_urls)
        if not saved_files:
            await message.reply("ɪᴍᴀɢᴇ ꜱᴀᴠᴇ ᴋᴀʀɴᴇ ᴍᴇ ᴅɪᴋᴋᴀᴛ ᴀᴀʏɪ!", reply_to_message_id=reply_to.id)
            await waiting_message.delete()
            return

        # Sabhi images ek saath bhej do
        media_group = [
            client.send_photo(chat_id=message.chat.id, photo=file, reply_to_message_id=reply_to.id)
            for file in saved_files
        ]
        await asyncio.gather(*media_group)

        # Images bhejne ke baad unhe delete karo
        for file in saved_files:
            os.remove(file)
    except Exception as e:
        await message.reply(f"ᴇʀʀᴏʀ ᴀᴀʏᴀ: {str(e)}", reply_to_message_id=reply_to.id)

    # Process complete hone ke baad "Image generate ho rahi hai..." message delete karo
    await waiting_message.delete()
