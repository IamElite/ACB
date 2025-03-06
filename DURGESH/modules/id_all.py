from pyrogram import filters
from pyrogram.enums import ParseMode
from DURGESH import app

@app.on_message(filters.command(["me", "e"], prefixes=["/", "!", ".", "M", "m"]))
async def ids(client, message):
    reply = message.reply_to_message
    if reply:
        await message.reply_text(
            f"ʏᴏᴜʀ ɪᴅ: {message.from_user.id}\n"
            f"{reply.from_user.first_name}'s ɪᴅ: {reply.from_user.id}\n"
            f"ᴄʜᴀᴛ ɪᴅ: {message.chat.id}"
        )
    else:
        await message.reply_text(
            f"ʏᴏᴜʀ ɪᴅ: {message.from_user.id}\n"
            f"ᴄʜᴀᴛ ɪᴅ: {message.chat.id}"
        )

@app.on_message(filters.command(["id", "d"], prefixes=["/", "!", ".", "I", "i"]))
async def getid(client, message):
    chat = message.chat
    your_id = message.from_user.id
    message_id = message.id
    reply = message.reply_to_message

    text = f"**[ᴍᴇssᴀɢᴇ ɪᴅ:]({message.link})** `{message_id}`\n"
    text += f"**[ʏᴏᴜʀ ɪᴅ:](tg://user?id={your_id})** `{your_id}`\n"

    if not message.command:
        message.command = message.text.split()

    if len(message.command) == 2:
        try:
            split = message.text.split(None, 1)[1].strip()
            user = await client.get_users(split)
            user_id = user.id
            text += f"**[ᴜsᴇʀ ɪᴅ:](tg://user?id={user_id})** `{user_id}`\n"
        except Exception:
            return await message.reply_text("ᴛʜɪs ᴜsᴇʀ ᴅᴏᴇsɴ'ᴛ ᴇxɪsᴛ.", quote=True)

    text += f"**[ᴄʜᴀᴛ ɪᴅ:](https://t.me/{chat.username})** `{chat.id}`\n\n"

    if reply and not getattr(reply, "empty", True) and not message.forward_from_chat and not reply.sender_chat:
        text += f"**[ʀᴇᴘʟɪᴇᴅ ᴍᴇssᴀɢᴇ ɪᴅ:]({reply.link})** `{reply.id}`\n"
        text += f"**[ʀᴇᴘʟɪᴇᴅ ᴜsᴇʀ ɪᴅ:](tg://user?id={reply.from_user.id})** `{reply.from_user.id}`\n\n"

    if reply and reply.forward_from_chat:
        text += f"ᴛʜᴇ ғᴏʀᴡᴀʀᴅᴇᴅ ᴄʜᴀɴɴᴇʟ, {reply.forward_from_chat.title}, ʜᴀs ᴀɴ ɪᴅ ᴏғ `{reply.forward_from_chat.id}`\n\n"
    if reply and reply.sender_chat:
        text += f"ɪᴅ ᴏғ ᴛʜᴇ ʀᴇᴘʟɪᴇᴅ ᴄʜᴀᴛ/ᴄʜᴀɴɴᴇʟ, ɪs `{reply.sender_chat.id}`"

    await message.reply_text(
        text,
        disable_web_page_preview=True,
        parse_mode=ParseMode.DEFAULT,
    )

@app.on_message(filters.command(["audioid", "udioid", "aid"], prefixes=["/", "!", ".", "A", "a"]) & filters.reply)
async def get_audio_id(client, message):
    reply_msg = message.reply_to_message
    if reply_msg and (reply_msg.audio or reply_msg.voice):
        audio = reply_msg.audio or reply_msg.voice
        file_id = audio.file_id
        await message.reply_text(f"Audio File ID: `{file_id}`")
    else:
        await message.reply_text("Please reply to an audio or voice message.")

@app.on_message(filters.command(["videoid", "ideoid", "vid"], prefixes=["/", "!", ".", "V", "v"]) & filters.reply)
async def get_video_id(client, message):
    reply_msg = message.reply_to_message
    if reply_msg and (reply_msg.video or reply_msg.video_note):
        video = reply_msg.video or reply_msg.video_note
        file_id = video.file_id
        await message.reply_text(f"Video File ID: `{file_id}`")
    else:
        await message.reply_text("Please reply to a video message.")
