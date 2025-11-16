import re, subprocess, os, urllib.request, tempfile
from io import BytesIO
from urllib.parse import urlparse, parse_qs, unquote
from pyrogram import filters
from DURGESH import app

def _get(m):
    return (m.reply_to_message.text.strip() if m.reply_to_message and m.reply_to_message.text
            else m.text.split(maxsplit=1)[1].strip() if len(m.command) >= 2 else None)

def _extract(u):
    q = parse_qs(urlparse(u).query); return unquote(q["imgurl"][0]) if "imgurl" in q else u

@app.on_message(filters.command(["thumbnail","thumb","t"], prefixes=["/","!",".",""]))
async def send_thumb(_, m):
    url = _get(m); 
    if not url: return await m.reply_text("give me image url")
    url = _extract(url)
    if not re.match(r"https?://", url): return await m.reply_text("invalid url")

    try:
        await m.delete()
        if m.reply_to_message: await m.reply_to_message.delete()
    except: pass

    wait = await m.reply_text("processing...")
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if not r.getheader("Content-Type","").startswith("image/"):
                return await wait.edit_text("url not image")
            data = r.read()
    except Exception:
        return await wait.edit_text("can't fetch url")

    in_f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg"); in_f.write(data); in_f.close()
    out_f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg"); out_f.close()

    try:
        subprocess.run(["convert", in_f.name,
                        "-modulate","100,115",
                        "-sigmoidal-contrast",
                        "4x50%","-enhance",
                        "-contrast-stretch",
                        "0.5%x0.5%", out_f.name], check=True)
        with open(out_f.name,"rb") as f: await m.reply_photo(f)
        await wait.delete()
    except Exception:
        try:
            bio = BytesIO(data); bio.name="img.jpg"; bio.seek(0)
            await m.reply_photo(bio); await wait.delete()
        except Exception:
            await wait.edit_text("error processing image")
    finally:
        for p in (in_f.name, out_f.name):
            if p and os.path.exists(p): os.remove(p)
