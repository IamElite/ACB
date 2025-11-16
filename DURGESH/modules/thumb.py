import re, subprocess, os, urllib.request, tempfile
from io import BytesIO
from urllib.parse import urlparse, parse_qs, unquote
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

def maybe_extract_imgurl(url: str) -> str:
    # handle google imgres (?imgurl=...), common redirect wrappers
    try:
        q = parse_qs(urlparse(url).query)
        if "imgurl" in q:
            return unquote(q["imgurl"][0])
    except:
        pass
    return url

def is_image_content(resp) -> bool:
    c = resp.getheader("Content-Type", "")
    return c.startswith("image/")

@app.on_message(filters.command(["thumbnail","thumb","t"], prefixes=["/","!",".", ""]))
async def send_thumb(_, m):
    url = extract_url(m)
    if not url:
        return await m.reply_text("give me any image url bro")

    url = maybe_extract_imgurl(url)

    if not re.match(r"https?://", url):
        return await m.reply_text("invalid url bro")

    try:
        await m.delete()
        if m.reply_to_message:
            await m.reply_to_message.delete()
    except:
        pass

    wait = await m.reply_text("processing...")

    infile_path = None
    outfile_path = None

    try:
        # add headers + timeout
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            if not is_image_content(resp):
                # not direct image -> fail early
                await wait.edit_text("error: url does not point to an image 😕")
                return

            data = resp.read()

        # write to temp infile for ImageMagick
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmpin:
            infile_path = tmpin.name
            tmpin.write(data)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmpout:
            outfile_path = tmpout.name

        # enhance with ImageMagick (may raise CalledProcessError)
        subprocess.run([
            "convert", infile_path,
            "-modulate", "100,115",
            "-sigmoidal-contrast", "4x50%",
            "-enhance",
            "-contrast-stretch", "0.5%x0.5%",
            outfile_path
        ], check=True)

        # send processed file
        with open(outfile_path, "rb") as f:
            await m.reply_photo(f)

        await wait.delete()

    except urllib.error.HTTPError as e:
        await wait.edit_text(f"http error: {e.code}")
    except urllib.error.URLError as e:
        await wait.edit_text("url error: can't reach host")
    except subprocess.CalledProcessError:
        # if convert not available or failed -> try sending raw bytes
        try:
            bio = BytesIO(data)
            bio.name = "img.jpg"
            bio.seek(0)
            await m.reply_photo(bio)
            await wait.delete()
        except Exception:
            await wait.edit_text("error: cannot process image or convert missing")
    except Exception as e:
        await wait.edit_text("error: couldn't process this link bro 😭")
    finally:
        for p in (infile_path, outfile_path):
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except:
                    pass
