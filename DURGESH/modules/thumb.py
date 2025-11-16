import re, subprocess, os, asyncio, urllib.request
from pyrogram import Client, filters
from DURGESH import app

def extract_url(m):
    return (
        m.reply_to_message.text.strip()
        if m.reply_to_message and m.reply_to_message.text
        else m.text.split(maxsplit=1)[1].strip()
        if len(m.command) >= 2
        else None
    )

@app.on_message(
    filters.command(["thumbnail","thumb","t"], prefixes=["/","!",".", ""])
)
async def send_thumb(_, m):
    url = extract_url(m)
    if not url:
        return await m.reply_text("give me any image url bro")

    if not re.match(r'https?://', url):
        return await m.reply_text("invalid url bro")

    try:
        await m.delete()
        if m.reply_to_message: 
            await m.reply_to_message.delete()
    except:
        pass

    wait = await m.reply_text("processing...")

    infile, outfile = "in.jpg", "out.jpg"

    try:
        img = urllib.request.urlopen(url).read()
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

    except:
        try:
            await m.reply_photo(url)
            await wait.delete()
        except:
            await wait.edit_text("error: can't process this link bro 😭")

    finally:
        for f in (infile, outfile):
            if os.path.exists(f):
                os.remove(f)
