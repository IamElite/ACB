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
        q = parse_qs(urlparse(u).query)
        if "imgurl" in q:
            return unquote(q["imgurl"][0])
    except:
        pass
    return u

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
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            if not _is_image_resp(r): return await wait.edit_text("url not image")
            data = r.read()
    except Exception:
        return await wait.edit_text("can't fetch url")
    await _process_and_send(m, data)
    await wait.delete()

# getall / ga — improved extraction
@app.on_message(filters.command(["getall","ga"], prefixes=["/","!",".",""]))
async def get_all_images(_, m):
    if not m.reply_to_message or not (m.reply_to_message.text or m.reply_to_message.caption):
        return await m.reply_text("reply karo us message ko jisme links hain")

    raw_text = m.reply_to_message.text or m.reply_to_message.caption or ""
    # unescape HTML entities (like &amp;)
    msg_text = html.unescape(raw_text)

    # 1) Telegram entities (text_link/url)
    entities = []
    if getattr(m.reply_to_message, "entities", None):
        entities += m.reply_to_message.entities
    if getattr(m.reply_to_message, "caption_entities", None):
        entities += m.reply_to_message.caption_entities

    urls = []
    for ent in entities:
        t = ent.type
        if t == "text_link" and getattr(ent, "url", None):
            urls.append(ent.url)
        elif t == "url":
            off, length = ent.offset, ent.length
            try:
                urls.append(msg_text[off:off+length])
            except:
                pass

    # 2) markdown-style [text]( url ) with optional spaces/newlines between ] and (
    md_links = re.findall(r'\[[^\]]+\]\s*\(\s*(https?://[^\s)]+)\s*\)', msg_text)
    if md_links:
        urls.extend(md_links)

    # 3) HTML <a ... href="..."> or href='...'
    html_links = re.findall(r'<a\s+[^>]*?href\s*=\s*([\'"])(https?://.*?)\1', msg_text, flags=re.IGNORECASE)
    if html_links:
        urls.extend([u for _, u in html_links])

    # 4) plain URLs fallback (captures urls inside () too)
    plain = re.findall(r'https?://[^\s)>\]]+', msg_text)
    if plain:
        urls.extend(plain)

    # sanitize & dedupe while preserving order
    seen = set(); final_urls = []
    for u in urls:
        if not u: continue
        u = u.strip(' \n\r\t\0\x0b\x1b')
        # remove numbering prefixes like "1." or "1)" at start
        u = re.sub(r'^[0-9]{1,3}[\.\)]\s*', '', u)
        # strip wrapping <> or trailing punctuation
        u = u.strip('<>.,;:()[]')
        u = u.replace("&amp;", "&")
        if u not in seen:
            seen.add(u); final_urls.append(u)

    if not final_urls:
        return await m.reply_text("koi url nahi mila us message mein")

    # debug: show what we found
    dbg = "\n".join(f"{i+1}. {u}" for i,u in enumerate(final_urls))
    wait = await m.reply_text(f"found {len(final_urls)} links:\n{dbg}\n\nprocessing...")

    MAX = 25
    if len(final_urls) > MAX:
        final_urls = final_urls[:MAX]
        await m.reply_text(f"zyaada links — pehle {MAX} hi process kar raha hoon")

    for idx, raw in enumerate(final_urls, 1):
        url = _extract_imgurl(raw)
        if not re.match(r"https?://", url):
            await m.reply_text(f"[{idx}] invalid: {url}"); continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                if not _is_image_resp(r):
                    await m.reply_text(f"[{idx}] not an image: {url}")
                    continue
                data = r.read()
            await _process_and_send(m, data)
            await asyncio.sleep(0.5)
        except Exception:
            await m.reply_text(f"[{idx}] failed: {url}")
    await wait.delete()
