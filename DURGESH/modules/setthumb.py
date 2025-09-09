from DURGESH import app
from DURGESH.database import db
from pyrogram import filters
from pyrogram.types import Message, ReplyParameters
from pyrogram.errors import ChatAdminRequired, UserNotParticipant
import time

thumb_col = db["thumb"]

@app.on_message(filters.command("st") & (filters.private | filters.group | filters.channel))
async def set_thumb(_, msg: Message):
    chat_id = msg.chat.id
    if msg.chat.type in ["group", "supergroup", "channel"]:
        try:
            member = await app.get_chat_member(chat_id, "me")
            if member.status not in ["administrator", "creator"]:
                return await msg.reply_text("⚠️ Bot ko ADMIN banao!")
        except UserNotParticipant:
            return await msg.reply_text("⚠️ Bot is chat ka member nahi hai!")
    reply = msg.reply_to_message
    if not reply:
        return await msg.reply_text("📸 Kisi photo ya image file pe reply karke /st likho!")
    file_id = None
    if reply.photo:
        file_id = reply.photo.file_id
    elif reply.document and reply.document.mime_type in ["image/jpeg", "image/png", "image/webp"]:
        file_id = reply.document.file_id
    if not file_id:
        return await msg.reply_text("❌ Sirf photo ya image file (jpg/png/webp) accept hoti hai!")
    await thumb_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "thumb_file_id": file_id,
            "chat_type": str(msg.chat.type),
            "title": msg.chat.title if msg.chat.title else msg.chat.first_name,
            "set_by": msg.from_user.id if msg.from_user else None,
            "set_at": int(time.time())
        }},
        upsert=True
    )
    await msg.reply_text(f"✅ Thumbnail Set for {msg.chat.type}!")

@app.on_message(filters.command("rt") & (filters.private | filters.group | filters.channel))
async def remove_thumb(_, msg: Message):
    chat_id = msg.chat.id
    if msg.chat.type in ["group", "supergroup", "channel"]:
        try:
            member = await app.get_chat_member(chat_id, "me")
            if member.status not in ["administrator", "creator"]:
                return await msg.reply_text("⚠️ Bot ko ADMIN banao!")
        except UserNotParticipant:
            return await msg.reply_text("⚠️ Bot is chat ka member nahi hai!")
    result = await thumb_col.delete_one({"chat_id": chat_id})
    await msg.reply_text(f"🗑️ Thumbnail Removed for {msg.chat.type}!" if result.deleted_count > 0 else "❌ Koi thumb nahi mili!")

async def get_thumb(chat_id: int) -> str:
    data = await thumb_col.find_one({"chat_id": chat_id})
    return data.get("thumb_file_id") if data else None

@app.on_message(filters.video & (filters.private | filters.group | filters.channel))
async def auto_apply_thumb(_, msg: Message):
    chat_id = msg.chat.id
    thumb = await get_thumb(chat_id)
    if not thumb:
        return
    try:
        sent = await msg.reply_video(
            video=msg.video.file_id,
            thumb=thumb,
            caption=msg.caption if msg.caption else "",
            caption_entities=msg.caption_entities if msg.caption else None,
            parse_mode=None,
            reply_parameters=ReplyParameters(message_id=msg.id)  # ← FIX: Deprecated warning removed
        )
        await msg.delete()
    except Exception as e:
        await msg.reply_text(f"❌ Thumbnail apply nahi hui: {str(e)}")
