import re
import os
import asyncio
import uuid
import tempfile
import subprocess
from io import BytesIO
from difflib import SequenceMatcher
from urllib.parse import quote_plus
import aiohttp
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.enums import ParseMode
from DURGESH import app

TMDB_ACCESS_TOKEN = ""
BASE_DIRECT = "https://api.themoviedb.org/3"
BASE_WORKER = "https://tmdbapi.the-zake.workers.dev/3"

if TMDB_ACCESS_TOKEN:
    BASE = BASE_DIRECT
    H = {"Authorization": f"Bearer {TMDB_ACCESS_TOKEN}", "accept": "application/json"}
else:
    BASE = BASE_WORKER
    H = {"accept": "application/json"}

IMG = "https://image.tmdb.org/t/p/"

POSTER_LIMIT = 40
BACKDROP_LIMIT = 40
LOGO_LIMIT = 15

POSTER_CACHE = {}
CACHE_EXPIRY = 180


def _cache_cleanup():
    now = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
    expired = [k for k, v in POSTER_CACHE.items() if now - v.get("ts", 0) > CACHE_EXPIRY]
    for k in expired:
        del POSTER_CACHE[k]


def _n(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def _similarity(a, b):
    return SequenceMatcher(None, _n(a), _n(b)).ratio()


async def _fetch_json(url, params=None):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=H, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            return await resp.json()


async def _search(q):
    t = q.strip()
    y = None
    m = re.search(r"(19|20)\d{2}$", t)
    if m:
        y = m.group(0)
        t = t[:-4].strip()
    
    async def do_search(query):
        results = []
        p1 = {"query": query, "include_adult": "false", "language": "en-US", "page": 1}
        r1 = await _fetch_json(f"{BASE}/search/multi", params=p1)
        results.extend(r1.get("results") or [])
        
        p2 = {"query": query, "include_adult": "false", "language": "en-US", "page": 1}
        r2 = await _fetch_json(f"{BASE}/search/movie", params=p2)
        for x in r2.get("results") or []:
            x["media_type"] = "movie"
            results.append(x)
        
        p3 = {"query": query, "include_adult": "false", "language": "en-US", "page": 1}
        r3 = await _fetch_json(f"{BASE}/search/tv", params=p3)
        for x in r3.get("results") or []:
            x["media_type"] = "tv"
            results.append(x)
        return results
    
    def generate_variations(word):
        variations = [word]
        vowels = "aeiou"
        word_lower = word.lower()
        for i, char in enumerate(word_lower):
            if char in vowels:
                for v in vowels:
                    if v != char:
                        new_word = word_lower[:i] + v + word_lower[i+1:]
                        if new_word not in variations:
                            variations.append(new_word)
        if len(word) > 3:
            for i in range(len(word_lower) - 1):
                swapped = word_lower[:i] + word_lower[i+1] + word_lower[i] + word_lower[i+2:]
                if swapped not in variations:
                    variations.append(swapped)
        return variations[:10]
    
    all_results = await do_search(t)
    
    if not all_results:
        variations = generate_variations(t)
        for var in variations[1:]:
            all_results = await do_search(var)
            if all_results:
                break
    
    seen_ids = set()
    res = []
    for x in all_results:
        if x.get("media_type") not in ("movie", "tv"):
            continue
        uid = (x.get("media_type"), x.get("id"))
        if uid not in seen_ids:
            seen_ids.add(uid)
            res.append(x)
    
    if not res:
        return None
    
    if y:
        flt = []
        for x in res:
            rd = x.get("release_date") or x.get("first_air_date") or ""
            yr = rd[:4] if rd else ""
            if yr == y:
                flt.append(x)
        if flt:
            res = flt
    
    nq = _n(t)
    best = None
    best_score = -1
    
    for x in res:
        mt = x.get("media_type")
        title = x.get("title") or x.get("name") or x.get("original_title") or x.get("original_name") or ""
        nt = _n(title)
        rd = x.get("release_date") or x.get("first_air_date") or ""
        yr = rd[:4] if rd else ""
        vc = x.get("vote_count", 0) or 0
        pop = x.get("popularity", 0) or 0
        
        sc = 0
        
        sim = _similarity(t, title)
        sc += int(sim * 5000)
        
        if len(nq) <= 3:
            if nt == nq:
                sc += 2000
            elif nq in nt:
                sc += 1000
        else:
            if nt == nq:
                sc += 6000
            elif nt.startswith(nq):
                sc += 4000
            elif nq.startswith(nt):
                sc += 3000
            elif nq in nt or nt in nq:
                sc += 2000
        
        if y and yr == y:
            sc += 8000
        
        sc += vc * 2
        sc += pop * 10
        
        if sc > best_score:
            best_score = sc
            best = (mt, x.get("id"), title, yr)
    
    return best


async def _get_details(kind, mid):
    if kind == "tv":
        url = f"{BASE}/tv/{mid}"
    else:
        url = f"{BASE}/movie/{mid}"
    r = await _fetch_json(url)
    
    lang_map = {"ja": "Japanese", "en": "English", "ko": "Korean", "hi": "Hindi", "zh": "Chinese", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese", "ru": "Russian", "th": "Thai", "ar": "Arabic", "te": "Telugu", "ta": "Tamil", "ml": "Malayalam", "kn": "Kannada", "bn": "Bengali", "mr": "Marathi", "pa": "Punjabi", "gu": "Gujarati"}
    
    orig_lang_code = r.get("original_language", "en")
    orig_lang_name = lang_map.get(orig_lang_code, "English")
    
    spoken = r.get("spoken_languages") or []
    if len(spoken) > 1:
        languages = f"{orig_lang_name}, Multiple Languages"
    else:
        languages = orig_lang_name
    
    return languages, orig_lang_code, orig_lang_name


async def _get_images(kind, mid, orig_lang="en"):
    if kind == "tv":
        url = f"{BASE}/tv/{mid}/images"
    else:
        url = f"{BASE}/movie/{mid}/images"
    
    r = await _fetch_json(url)
    
    posters_raw = r.get("posters", []) or []
    backs_raw = r.get("backdrops", []) or []
    logos_raw = r.get("logos", []) or []
    
    posters_raw.sort(key=lambda z: z.get("vote_count", 0), reverse=True)
    backs_raw.sort(key=lambda z: z.get("vote_count", 0), reverse=True)
    logos_raw.sort(key=lambda z: z.get("vote_count", 0), reverse=True)
    
    lang_map = {"ja": "Japanese", "en": "English", "ko": "Korean", "hi": "Hindi", "zh": "Chinese", "es": "Spanish", "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese", "ru": "Russian", "th": "Thai", "ar": "Arabic", "te": "Telugu", "ta": "Tamil", "ml": "Malayalam", "kn": "Kannada", "bn": "Bengali", "mr": "Marathi", "pa": "Punjabi", "gu": "Gujarati"}
    
    available_langs = {}
    for x in backs_raw:
        lang = x.get("iso_639_1")
        if lang and lang != "en" and lang in lang_map:
            if lang not in available_langs:
                available_langs[lang] = []
            available_langs[lang].append(x)
    
    best_lang = orig_lang
    best_lang_name = lang_map.get(orig_lang, "English")
    best_backs = []
    
    if orig_lang in available_langs:
        best_backs = available_langs[orig_lang]
    elif available_langs:
        best_lang = max(available_langs.keys(), key=lambda l: len(available_langs[l]))
        best_lang_name = lang_map.get(best_lang, best_lang.upper())
        best_backs = available_langs[best_lang]
    
    d = {
        "orig_landscape": [IMG + "original" + x["file_path"] for x in best_backs[:BACKDROP_LIMIT]],
        "orig_lang_name": best_lang_name,
        "all_landscape": [IMG + "original" + x["file_path"] for x in backs_raw[:BACKDROP_LIMIT]],
        "all_posters": [IMG + "original" + x["file_path"] for x in posters_raw[:POSTER_LIMIT]],
        "all_logos": [IMG + "original" + x["file_path"] for x in logos_raw[:LOGO_LIMIT]],
    }
    return d


POSTER_TEMPLATE = """<b>Search Result</b>
<b>Query:</b> {query}
<b>Title:</b> {title}
<b>Languages:</b> {languages}

<b>{orig_lang_name} Landscape ({orig_land_count} images):</b>
{orig_landscape}

<b>All Landscape ({all_land_count} images):</b>
{all_landscape}

<b>All Posters ({poster_count} images):</b>
{posters}

<b>All Logos ({logo_count} images):</b>
{logos}

<b>Total:</b> {total} quality links
<b>Limits:</b> Landscapes/Posters (1-40), Logos (1-15)

<i>Click buttons to download images:</i>"""


@app.on_message(filters.command("p", prefixes=["/", "!", ".", ""]))
async def poster_cmd(client, message):
    if not getattr(message, "command", None) or len(message.command) < 2:
        return await message.reply_text(
            "<b>🎬 Poster Scraper</b>\n\n"
            "<b>Usage:</b> <code>/p movie_name</code>\n\n"
            "<b>Features:</b>\n"
            "• Auto spelling correction\n"
            "• Landscapes/Posters: up to 40\n"
            "• Logos: up to 15\n"
            "• Full HD Quality\n\n"
            "<b>Examples:</b>\n"
            "<code>/p Spiderman</code> → Spider-Man\n"
            "<code>/p Wednsday</code> → Wednesday",
            parse_mode=ParseMode.HTML
        )
    q = " ".join(message.command[1:])
    w = await message.reply_text(f"<i>🔍 Searching:</i>\n<code>{q}</code>", parse_mode=ParseMode.HTML)
    r = await _search(q)
    if not r:
        return await w.edit_text("<b>❌ Not Found</b>\n<i>Try with correct spelling or year</i>", parse_mode=ParseMode.HTML)
    kind, mid, title, year = r
    await w.edit_text(f"<i>📥 Fetching posters for:</i>\n<b>{title}</b> ({year})", parse_mode=ParseMode.HTML)
    languages, orig_lang_code, orig_lang_name = await _get_details(kind, mid)
    imgs = await _get_images(kind, mid, orig_lang_code)
    
    t = f"{title}"
    if year:
        t += f" ({year})"
    
    _cache_cleanup()
    cache_id = str(uuid.uuid4())[:8]
    POSTER_CACHE[cache_id] = {
        "title": t,
        "orig_landscape": imgs["orig_landscape"],
        "all_landscape": imgs["all_landscape"],
        "all_posters": imgs["all_posters"],
        "all_logos": imgs["all_logos"],
        "orig_lang_name": imgs.get("orig_lang_name", orig_lang_name),
        "ts": asyncio.get_event_loop().time()
    }
    
    def format_links(urls):
        if not urls:
            return "No images found"
        if len(urls) == 1:
            return urls[0]
        lines = []
        first_link = urls[0]
        for i, x in enumerate(urls[1:], 2):
            lines.append(f'{i}. <a href="{x}">HD Link</a>')
        rest = "\n".join(lines)
        return f"{first_link}\n<blockquote expandable>{rest}</blockquote>"
    
    orig_land = format_links(imgs["orig_landscape"])
    all_land = format_links(imgs["all_landscape"])
    posters = format_links(imgs["all_posters"])
    logos = format_links(imgs["all_logos"])
    
    olname = imgs.get("orig_lang_name", orig_lang_name)
    total = len(imgs["all_landscape"]) + len(imgs["all_posters"]) + len(imgs["all_logos"])
    
    text = POSTER_TEMPLATE.format(
        query=q,
        title=t,
        languages=languages,
        orig_lang_name=olname,
        orig_landscape=orig_land,
        all_landscape=all_land,
        posters=posters,
        logos=logos,
        orig_land_count=len(imgs["orig_landscape"]),
        all_land_count=len(imgs["all_landscape"]),
        poster_count=len(imgs["all_posters"]),
        logo_count=len(imgs["all_logos"]),
        total=total
    )
    
    buttons = []
    if imgs["orig_landscape"]:
        buttons.append(InlineKeyboardButton(f"📐 {olname} ({len(imgs['orig_landscape'])})", callback_data=f"pdl_{cache_id}_orig"))
    if imgs["all_landscape"]:
        buttons.append(InlineKeyboardButton(f"🖼 Landscape ({len(imgs['all_landscape'])})", callback_data=f"pdl_{cache_id}_land"))
    if imgs["all_posters"]:
        buttons.append(InlineKeyboardButton(f"🎬 Posters ({len(imgs['all_posters'])})", callback_data=f"pdl_{cache_id}_post"))
    if imgs["all_logos"]:
        buttons.append(InlineKeyboardButton(f"✨ Logos ({len(imgs['all_logos'])})", callback_data=f"pdl_{cache_id}_logo"))
    
    keyboard = []
    for i in range(0, len(buttons), 2):
        keyboard.append(buttons[i:i+2])
    
    hc_status = POSTER_CACHE[cache_id].get("hc", True)
    hc_text = "🔆 HD Enhance: ON" if hc_status else "🔅 HD Enhance: OFF"
    keyboard.append([InlineKeyboardButton(hc_text, callback_data=f"phc_{cache_id}")])
    
    await w.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=False)


@app.on_callback_query(filters.regex(r"^pdl_"))
async def poster_download_callback(client, callback_query):
    data = callback_query.data
    parts = data.split("_")
    if len(parts) < 3:
        return await callback_query.answer("Invalid request!", show_alert=True)
    
    cache_id = parts[1]
    img_type = parts[2]
    
    if cache_id not in POSTER_CACHE:
        return await callback_query.answer("Session expired! Use /p again", show_alert=True)
    
    cache = POSTER_CACHE[cache_id]
    title = cache["title"]
    
    if img_type == "orig":
        urls = cache["orig_landscape"]
        label = f"{cache['orig_lang_name']} Landscape"
    elif img_type == "land":
        urls = cache["all_landscape"]
        label = "All Landscape"
    elif img_type == "post":
        urls = cache["all_posters"]
        label = "Posters"
    elif img_type == "logo":
        urls = cache["all_logos"]
        label = "Logos"
    else:
        return await callback_query.answer("Invalid type!", show_alert=True)
    
    if not urls:
        return await callback_query.answer("No images found!", show_alert=True)
    
    hc_enabled = cache.get("hc", True)
    await callback_query.answer(f"Sending {len(urls)} {label}..." + (" (Enhanced)" if hc_enabled else ""))
    
    chat_id = callback_query.message.chat.id
    
    async def download_image(url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    return await resp.read()
        return None
    
    async def process_image(data):
        if not hc_enabled:
            return data
        in_f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        in_f.write(data)
        in_f.close()
        out_f = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        out_f.close()
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                ["convert", in_f.name,
                 "-modulate", "100,115", "-sigmoidal-contrast", "4x50%", "-enhance",
                 "-contrast-stretch", "0.5%x0.5%", out_f.name],
                check=True, capture_output=True
            )
            with open(out_f.name, "rb") as f:
                return f.read()
        except Exception:
            return data
        finally:
            for p in (in_f.name, out_f.name):
                if p and os.path.exists(p):
                    os.remove(p)
    
    for i in range(0, len(urls), 10):
        batch = urls[i:i+10]
        try:
            media = []
            for j, url in enumerate(batch):
                img_data = await download_image(url)
                if img_data:
                    processed = await process_image(img_data)
                    bio = BytesIO(processed)
                    bio.name = f"img_{i+j+1}.jpg"
                    if j == 0:
                        media.append(InputMediaPhoto(bio, caption=f"<b>{title}</b>\n{label} ({i+1}-{i+len(batch)}/{len(urls)})", parse_mode=ParseMode.HTML))
                    else:
                        media.append(InputMediaPhoto(bio))
            if len(media) == 1:
                await client.send_photo(chat_id, media[0].media, caption=media[0].caption, parse_mode=ParseMode.HTML)
            elif media:
                await client.send_media_group(chat_id, media)
        except Exception as e:
            await client.send_message(chat_id, f"<b>Error batch {i//10 + 1}:</b> {str(e)[:100]}", parse_mode=ParseMode.HTML)
        
        if i + 10 < len(urls):
            await asyncio.sleep(1)


@app.on_callback_query(filters.regex(r"^phc_"))
async def hc_toggle_callback(client, callback_query):
    cache_id = callback_query.data.split("_")[1]
    if cache_id not in POSTER_CACHE:
        return await callback_query.answer("Session expired!", show_alert=True)
    
    cache = POSTER_CACHE[cache_id]
    cache["hc"] = not cache.get("hc", True)
    hc_status = cache["hc"]
    
    msg = callback_query.message
    keyboard = msg.reply_markup.inline_keyboard[:-1]
    
    hc_text = "🔆 HD Enhance: ON" if hc_status else "🔅 HD Enhance: OFF"
    keyboard.append([InlineKeyboardButton(hc_text, callback_data=f"phc_{cache_id}")])
    
    await msg.edit_reply_markup(InlineKeyboardMarkup(keyboard))
    await callback_query.answer(f"HD Enhance: {'ON' if hc_status else 'OFF'}")

