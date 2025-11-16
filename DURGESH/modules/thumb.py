import re, subprocess, os, urllib.request, tempfile, asyncio
from io import BytesIO
from urllib.parse import urlparse, parse_qs, unquote
from pyrogram import filters
from DURGESH import app

# tiny helpers
def _get(m):
    return (m.reply_to_message.text.strip() if m.reply_to_message and m.reply_to_message.text
            else m.text.split(maxsplit=1)[1].strip() if len(m.command) >= 2 else None)

def _extract(u):
    q = parse_qs(urlparse(u).query)
    return unquote(q["imgurl"][0]) if "imgurl" in q else u

def _is_image_resp(r): return r.getheader("Content-Type","").startswith("image/")

async def _process_and_send(m_target, data):
    in_f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg"); in_f.write(data); in_f.close()
    out_f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg"); out_f.close()
    try:
        subprocess.run(["convert", in_f.name,
                        "-modulate","100,115","-sigmoidal-contrast","4x50%","-enhance",
                        "-contrast-stretch","0.5%x0.5%", out_f.name], check=True)
        with open(out_f.name,"rb") as f: await m_target.reply_photo(f)
    except Exception:
        bio = BytesIO(data); bio.name="img.jpg"; bio.seek(0)
        await m_target.reply_photo(bio)
    finally:
        for p in (in_f.name, out_f.name):
            if p and os.path.exists(p): os.remove(p)

# single-url command (same as before)
@app.on_message(filters.command(["thumbnail","thumb","t"], prefixes=["/","!",".",""]))
async def send_thumb(_, m):
    url = _get(m)
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
            if not _is_image_resp(r): return await wait.edit_text("url not image")
            data = r.read()
    except Exception:
        return await wait.edit_text("can't fetch url")
    await _process_and_send(m, data)
    await wait.delete()

# new: getall / ga — reply to a message that contains many links
@app.on_message(filters.command(["getall","ga"], prefixes=["/","!",".",""]))
async def get_all_images(_, m):
    if not m.reply_to_message or not (m.reply_to_message.text or m.reply_to_message.caption):
        return await m.reply_text("reply karo us message ko jisme links hain")

    # collect text + entities (works for text and caption)
    msg_text = m.reply_to_message.text or m.reply_to_message.caption or ""
    entities = []
    if getattr(m.reply_to_message, "entities", None):
        entities += m.reply_to_message.entities
    if getattr(m.reply_to_message, "caption_entities", None):
        entities += m.reply_to_message.caption_entities

    urls = []
    # first extract from entity objects (handles clickable hyperlinks)
    for ent in entities:
        t = ent.type
        if t == "text_link" and getattr(ent, "url", None):
            urls.append(ent.url)
        elif t == "url":
            # offset/length give substring
            off, length = ent.offset, ent.length
            urls.append(msg_text[off:off+length])

    # fallback: regex to catch plain links in visible text
    if not urls:
        urls = re.findall(r'https?://[^\s)>\]]+', msg_text)

    if not urls:
        return await m.reply_text("koi url nahi mila us message mein")

    MAX = 10
    if len(urls) > MAX:
        urls = urls[:MAX]
        await m.reply_text(f"zyaada links — pehle {MAX} hi process kar raha hoon")

    wait = await m.reply_text(f"found {len(urls)} links — processing...")
    for idx, raw in enumerate(urls, 1):
        url = _extract(raw.strip('.,;:()[]<>'))
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                if not _is_image_resp(r):
                    await m.reply_text(f"[{idx}] not an image: {url}")
                    continue
                data = r.read()
            await _process_and_send(m, data)
            await asyncio.sleep(0.7)
        except Exception:
            await m.reply_text(f"[{idx}] failed: {url}")
    await wait.delete()
