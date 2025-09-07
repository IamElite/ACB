import re, subprocess, os, asyncio, urllib.request
from pyrogram import Client, filters
from DURGESH import app
from config import ADMINS

def get_best_thumb(url):
    vid=re.search(r"(?:v=|\.be/)([a-zA-Z0-9_-]{11})",url)
    return f"https://i.ytimg.com/vi/{vid.group(1)}/maxresdefault.jpg"if vid else None

@app.on_message(filters.command(["thumbnail","thumb","t"], prefixes=["/","!",".", ""]) & filters.user(ADMINS))
async def send_thumb(_,m):
    url=(m.reply_to_message.text.strip()if m.reply_to_message and m.reply_to_message.text else m.text.split(maxsplit=1)[1].strip()if len(m.command)>=2 else None)
    if not url:return await m.reply_text("ɢɪᴠᴇ ᴍᴇ ᴀ ʏᴛ ᴜʀʟ")
    if not re.search(r"(?:youtube\.com|youtu\.be)",url):return await m.reply_text("ɪɴᴠᴀʟɪᴅ ʏᴏᴜᴛᴜʙᴇ ʟɪɴᴋ")
    try:await m.delete();await m.reply_to_message.delete()
    except:pass
    wait=await m.reply_text("ᴘʀᴏᴄᴇssɪɴɢ...")
    thumb=get_best_thumb(url)
    if not thumb:return await wait.edit_text("ᴛʜᴜᴍʙɴᴀɪʟ ɴᴏᴛ ғᴏᴜɴᴅ")
    try:
        img = urllib.request.urlopen(thumb).read()
        infile, outfile = "in.jpg", "out.jpg"
        with open(infile, "wb") as f:
            f.write(img)
        subprocess.run([
            "convert", infile,
            "-modulate", "100,115",
            "-sigmoidal-contrast", "4x50%",
            "-enhance",
            "-contrast-stretch", "0.5%x0.5%",
            outfile
        ], check=True)
        with open(outfile, "rb") as f:
            await m.reply_photo(f)
        await wait.delete()
    except FileNotFoundError:
        await m.reply_photo(thumb)
        await wait.delete()
    except Exception:
        await wait.edit_text("ᴇʀʀᴏʀ")
    finally:
        for f in (infile, outfile):
            if os.path.exists(f):
                os.remove(f)
