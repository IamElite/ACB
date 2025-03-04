import asyncio
from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from DURGESH import app
from DURGESH.database import get_chats
from config import OWNER_ID

@app.on_message(filters.command("broadcast") & filters.user(OWNER_ID))
async def broadcast_(_, message: Message):
    """Broadcasts a single message to all chats and users, with automatic pinning in groups."""

    reply = message.reply_to_message
    text = message.text.split(None, 1)[1] if len(message.command) > 1 else None

    if not reply and not text:
        return await message.reply_text("❖ Reply to a message or provide text to broadcast.")

    progress_msg = await message.reply_text("❖ Broadcasting message Please wait...")

    sent_groups, sent_users, failed, pinned = 0, 0, 0, 0
    data = await get_chats()
    
    recipients = data["chats"] + data["users"]

    for chat_id in recipients:
        try:
            msg = await (reply.copy(chat_id) if reply else app.send_message(chat_id, text=text))
            
            if chat_id < 0:  # Group chat
                try:
                    await msg.pin(disable_notification=True)
                    pinned += 1
                except:
                    pass  
                sent_groups += 1
            else:
                sent_users += 1

            await asyncio.sleep(0.2)  # Prevent rate limits

        except FloodWait as fw:
            await asyncio.sleep(fw.value + 1)
        except:
            failed += 1  

    await progress_msg.edit_text(
        f"✅ Broadcast completed.\n\n"
        f"👥 Groups Sent: {sent_groups}\n"
        f"🧑‍💻 Users Sent: {sent_users}\n"
        f"📌 Pinned: {pinned}\n"
        f"❌ Failed: {failed}"
    )