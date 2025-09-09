# thumb.py  (or whatever name you use inside DURGESH folder)
from DURGESH import app
from DURGESH.database import db
from pyrogram import Client, filters
from pyrogram.types import Message, ReplyParameters
from pyrogram.errors import ChatAdminRequired, UserNotParticipant
import time


thumb_col = db["thumb"]

# ---------- SET THUMB ----------
@app.on_message(filters.command("st") & (filters.private | filters.group | filters.channel))
async def set_thumb(_, msg: Message):
    chat_id = msg.chat.id

    # admin check for groups/channels
    if msg.chat.type in {"group", "supergroup", "channel"}:
        try:
            member = await app.get_chat_member(chat_id, "me")
            if member.status not in {"administrator", "creator"}:
                return await msg.reply("⚠️ Bot ko ADMIN banao!")
        except UserNotParticipant:
            return await msg.reply("⚠️ Bot is chat ka member nahi hai!")

    reply = msg.reply_to_message
    if not reply:
        return await msg.reply("📸 Kisi photo ya image file pe reply karke /st likho!")

    file_id = None
    if reply.photo:
        file_id = reply.photo.file_id
    elif reply.document and reply.document.mime_type in {"image/jpeg", "image/png", "image/webp"}:
        file_id = reply.document.file_id

    if not file_id:
        return await msg.reply("❌ Sirf photo ya image file (jpg/png/webp) accept hoti hai!")

    await thumb_col.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "thumb_file_id": file_id,
            "chat_type": str(msg.chat.type),
            "title": msg.chat.title or msg.chat.first_name,
            "set_by": msg.from_user.id if msg.from_user else None,
            "set_at": int(time.time())
        }},
        upsert=True
    )
    await msg.reply(f"✅ Thumbnail Set for {msg.chat.type}!")


# ---------- REMOVE THUMB ----------
@app.on_message(filters.command("rt") & (filters.private | filters.group | filters.channel))
async def remove_thumb(_, msg: Message):
    chat_id = msg.chat.id

    if msg.chat.type in {"group", "supergroup", "channel"}:
        try:
            member = await app.get_chat_member(chat_id, "me")
            if member.status not in {"administrator", "creator"}:
                return await msg.reply("⚠️ Bot ko ADMIN banao!")
        except UserNotParticipant:
            return await msg.reply("⚠️ Bot is chat ka member nahi hai!")

    result = await thumb_col.delete_one({"chat_id": chat_id})
    await msg.reply(
        f"🗑️ Thumbnail Removed for {msg.chat.type}!" if result.deleted_count else "❌ Koi thumb nahi mili!"
    )


# ---------- UTIL ----------
async def get_thumb(chat_id: int) -> str | None:
    doc = await thumb_col.find_one({"chat_id": chat_id})
    return doc.get("thumb_file_id") if doc else None


# ---------- AUTO APPLY (FIXED) ----------
import asyncio, os, tempfile
from pyrogram.types import InputMediaVideo

@app.on_message(filters.video & (filters.private | filters.group | filters.channel))
async def auto_apply_thumb(_, msg: Message):
    chat_id = msg.chat.id
    thumb_file_id = await get_thumb(chat_id)
    if not thumb_file_id:
        return  # no custom thumb set

    # 1. download thumb
    thumb_path = await app.download_media(thumb_file_id)

    status = await msg.reply("🔄 Thumbnail lagaya ja raha hai…")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
        video_path = tmp.name

    try:
        # 2. download video
        await app.download_media(msg.video.file_id, file_name=video_path)
        # 3. re-upload with thumb
        await msg.reply_video(
            video=video_path,
            thumb=thumb_path,
            caption=msg.caption or "",
            caption_entities=msg.caption_entities if msg.caption else None,
            parse_mode=None,
            duration=msg.video.duration,
            width=msg.video.width,
            height=msg.video.height,
            supports_streaming=True,
            reply_parameters=ReplyParameters(message_id=msg.id)
        )
    except Exception as e:
        await msg.reply(f"❌ Thumbnail apply nahi hua: {str(e)}")
    else:
        await msg.delete()
    finally:
        await status.delete()
        # clean up
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(thumb_path):
            os.remove(thumb_path)
