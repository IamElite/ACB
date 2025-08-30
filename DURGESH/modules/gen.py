# gen.py  (plug-in module, no Client creation)
from pyrogram import filters
from pyrogram.types import Message
from DURGESH import app                # already-made Client
import requests, tempfile, os

TG_TOKEN  = "d3b25feccb89e508a9114afb82aa421fe2a9712b963b387cc5ad71e58722"
CATBOX_URL = "https://catbox.moe/user/api.php"

@app.on_message(filters.command("gen"))
async def gen_post(_, msg: Message):
    if not msg.reply_to_message or not msg.reply_to_message.photo:
        return await msg.reply("❗ Kisi photo pe reply karo `/gen` se.")

    photo  = msg.reply_to_message.photo.file_id
    caption = (msg.reply_to_message.caption or "").strip()
    title   = caption[:256] or "Untitled"
    author  = msg.from_user.first_name or ""

    status = await msg.reply("📤 Uploading to Catbox…")
    tmp_path = await app.download_media(photo)

    with open(tmp_path, "rb") as f:
        catbox_resp = requests.post(
            CATBOX_URL,
            data={"reqtype": "fileupload", "json": "true"},
            files={"fileToUpload": f},
            timeout=30
        )
    os.remove(tmp_path)

    try:
        catbox_url = catbox_resp.text.strip()
        assert catbox_url.startswith("http")
    except Exception:
        return await status.edit("❌ Catbox upload failed.")

    content = [
        {"tag": "img", "attrs": {"src": catbox_url, "alt": title}},
        {"tag": "br"},
        {"tag": "p", "children": [caption]}
    ]

    tg_resp = requests.post(
        "https://api.telegra.ph/createPage",
        json={
            "access_token": TG_TOKEN,
            "title": title,
            "author_name": author,
            "content": content
        },
        timeout=15
    ).json()

    if tg_resp.get("ok"):
        url = tg_resp["result"]["url"]
        await status.edit(f"✅ Telegraph page ready: [Link]({url})", disable_web_page_preview=True)
    else:
        await status.edit("❌ Telegraph error: " + str(tg_resp))
