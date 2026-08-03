import re, subprocess, os, urllib.request, tempfile, asyncio, html
from io import BytesIO
from urllib.parse import urlparse, parse_qs, unquote
from pyrogram import filters
from DURGESH import app

# helpers
def _get(m):
    return (m.reply_to_message.text.strip() if m.reply_to_message and m.reply_to_message.text
            else m.text.split(maxsplit=1)[1].strip() if len(m.command) >= 2 else None)

def _extract_imgurl(u):
    try:
        parsed = urlparse(u)
        if parsed.netloc in ('youtu.be', 'www.youtu.be', 'youtube.com', 'www.youtube.com', 'm.youtube.com'):
            vid = parsed.path.strip('/').split('/')[-1] if (parsed.netloc in ('youtu.be', 'www.youtu.be') or '/shorts/' in parsed.path or '/embed/' in parsed.path) else parse_qs(parsed.query).get('v', [None])[0]
            if vid:
                return f"https://img.youtube.com/vi/{vid}/maxresdefault.jpg"
        q = parse_qs(parsed.query)
        if "imgurl" in q:
            return unquote(q["imgurl"][0])
    except:
        pass
    return u

def _download_url_data(url):
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read(), r.getheader("Content-Type", "")
    except Exception:
        if "maxresdefault.jpg" in url:
            try:
                fallback_url = url.replace("maxresdefault.jpg", "hqdefault.jpg")
                req = urllib.request.Request(fallback_url, headers={"User-Agent":"Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as r:
                    return r.read(), r.getheader("Content-Type", "")
            except Exception:
                pass
        raise

async def _process_and_send(m_target, data):
    inf, outf = tempfile.mktemp(".jpg"), tempfile.mktemp(".jpg")
    try:
        with open(inf, "wb") as f: f.write(data)
        subprocess.run(["convert", inf, "-modulate", "100,115", "-sigmoidal-contrast", "4x50%", "-enhance", "-contrast-stretch", "0.5%x0.5%", outf], check=True)
        await m_target.reply_photo(outf)
    except Exception:
        bio = BytesIO(data); bio.name="img.jpg"
        await m_target.reply_photo(bio)
    finally:
        for p in (inf, outf):
            if os.path.exists(p): os.remove(p)

# single-url command
@app.on_message(filters.command(["thumbnail","thumb","t"], prefixes=["/","!",".",""]))
async def send_thumb(_, m):
    url = _get(m)
    if not url: return await m.reply_text("give me image url")
    url = _extract_imgurl(url.strip(' \n\r\t\0\x0b\x1b.,;:()[]<>'))
    if not re.match(r"https?://", url): return await m.reply_text("invalid url")

    try:
        await m.delete()
        if m.reply_to_message: await m.reply_to_message.delete()
    except: pass

    wait = await m.reply_text("processing...")
    try:
        data, content_type = _download_url_data(url)
        if not content_type.startswith("image/"):
            return await wait.edit_text("url not image")
    except Exception:
        return await wait.edit_text("can't fetch url")
    await _process_and_send(m, data)
    await wait.delete()

# getall / ga
@app.on_message(filters.command(["getall","ga"], prefixes=["/","!",".",""]))
async def get_all_images(_, m):
    if not m.reply_to_message or not (m.reply_to_message.text or m.reply_to_message.caption):
        return await m.reply_text("reply karo us message ko jisme links hain")

    raw_text = html.unescape(m.reply_to_message.text or m.reply_to_message.caption or "")
    urls = []
    for ent in (getattr(m.reply_to_message, "entities", None) or []) + (getattr(m.reply_to_message, "caption_entities", None) or []):
        if ent.type == "text_link": urls.append(ent.url)
        elif ent.type == "url": urls.append(raw_text[ent.offset : ent.offset + ent.length])

    urls += re.findall(r'\[[^\]]+\]\s*\(\s*(https?://[^\s)]+)\s*\)', raw_text)
    urls += [u for _, u in re.findall(r'<a\s+[^>]*?href\s*=\s*([\'"])(https?://.*?)\1', raw_text, re.I)]
    urls += re.findall(r'https?://[^\s)>\]]+', raw_text)

    seen = set(); final_urls = []
    for u in urls:
        if not u: continue
        u = re.sub(r'^[0-9]{1,3}[\.\)]\s*', '', u.strip(' \n\r\t\0\x0b\x1b')).strip('<>.,;:()[]').replace("&amp;", "&")
        if u not in seen:
            seen.add(u); final_urls.append(u)

    if not final_urls: return await m.reply_text("koi url nahi mila us message mein")

    dbg = "\n".join(f"{i+1}. {u}" for i, u in enumerate(final_urls))
    wait = await m.reply_text(f"found {len(final_urls)} links:\n{dbg}\n\nprocessing...")

    if len(final_urls) > 25:
        final_urls = final_urls[:25]
        await m.reply_text("zyaada links — pehle 25 hi process kar raha hoon")

    for idx, raw in enumerate(final_urls, 1):
        url = _extract_imgurl(raw)
        if not re.match(r"https?://", url):
            await m.reply_text(f"[{idx}] invalid: {url}"); continue
        try:
            data, content_type = _download_url_data(url)
            if not content_type.startswith("image/"):
                await m.reply_text(f"[{idx}] not an image: {url}"); continue
            await _process_and_send(m, data)
            await asyncio.sleep(0.5)
        except Exception:
            await m.reply_text(f"[{idx}] failed: {url}")
    await wait.delete()
