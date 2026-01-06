import re, os, asyncio, uuid, tempfile, subprocess, aiohttp

from io import BytesIO
from difflib import SequenceMatcher
from urllib.parse import quote_plus

from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.enums import ParseMode
from DURGESH import app

TMDB_ACCESS_TOKEN = ""
BASE_DIRECT = "https://api.themoviedb.org/3"
BASE_WORKER = "https://tmdbapi.the-zake.workers.dev/3"

CRUNCHYROLL_API = "https://crunchyroll.blaze-updatez.workers.dev/?q="

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

OTT_WORKERS = {
    "zee5.com": "https://zee5.the-zake.workers.dev/?url=",
    "tv.apple.com": "https://appletv.the-zake.workers.dev/?url=",
    "airtelxstream.in": "https://airtelxstream.the-zake.workers.dev/?url=",
    "sunnxt.com": "https://sunnxt.the-zake.workers.dev/?url=",
    "aha.video": "https://ahavideo.the-zake.workers.dev/?url=",
    "iqiyi.com": "https://iqiyi.the-zake.workers.dev/?url=",
    "wetv.vip": "https://wetv.the-zake.workers.dev/?url=",
    "shemaroome.com": "https://shemaroo.the-zake.workers.dev/?url=",
    "bookmyshow.com": "https://bookmyshow.the-zake.workers.dev/?url=",
    "plex.tv": "https://plextv.the-zake.workers.dev/?url=",
    "addatimes.com": "https://addatimes.the-zake.workers.dev/?url=",
    "thestage.in": "https://stage.the-zake.workers.dev/?url=",
    "netflix.com": "https://netflix.the-zake.workers.dev/?url=",
    "mxplayer.in": "https://mxplayer.the-zake.workers.dev/?url=",
    "primevideo.com": "https://primevideo.pbx1bots.workers.dev/?url=",
    "amazon.com": "https://primevideo.pbx1bots.workers.dev/?url=",
    "crunchyroll.com": "https://crunchyroll.blaze-updatez.workers.dev/?q=",
}

OTT_NAMES = {
    "zee5.com": "ZEE5", "tv.apple.com": "Apple TV+", "airtelxstream.in": "Airtel Xstream",
    "sunnxt.com": "Sun NXT", "aha.video": "Aha Video", "iqiyi.com": "iQIYI",
    "wetv.vip": "WeTV", "shemaroome.com": "ShemarooMe", "bookmyshow.com": "BookMyShow",
    "plex.tv": "Plex TV", "addatimes.com": "Addatimes", "thestage.in": "Stage",
    "netflix.com": "Netflix", "mxplayer.in": "MX Player", "primevideo.com": "Prime Video",
    "amazon.com": "Prime Video", "crunchyroll.com": "Crunchyroll",
}



def _detect_ott_platform(url):
    url_lower = url.lower()
    for domain in OTT_WORKERS:
        if domain in url_lower:
            return domain
    return None


async def _fetch_ott_info(url, platform):
    worker = OTT_WORKERS.get(platform)
    if not worker:
        return None
    try:
        if platform == "crunchyroll.com":
            # For CR, try to extract the query from URL if it's a URL, otherwise use as is
            query = url
            if "crunchyroll.com/" in url:
                path = url.split("crunchyroll.com/")[-1].strip("/")
                if path:
                    query = path.split("/")[0].replace("-", " ")
            fetch_url = f"{CRUNCHYROLL_API}{quote_plus(query)}"
        else:
            fetch_url = f"{worker}{quote_plus(url)}"
            
        async with aiohttp.ClientSession() as session:
            async with session.get(fetch_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                root = data.get("data", data)
                images = data.get("images", {}) or {}
                return {
                    "title": root.get("title", "Unknown"),
                    "year": str(root.get("year", root.get("metadata", {}).get("release_year", ""))),
                    "poster": root.get("portrait") or root.get("poster") or images.get("portrait_poster"),
                    "landscape": root.get("landscape") or root.get("banner") or images.get("landscape_poster") or images.get("banner_backdrop"),
                    "source": OTT_NAMES.get(platform, platform)
                }
    except:
        return None


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
    
    en_backs = [x for x in backs_raw if x.get("iso_639_1") == "en"]
    hi_backs = [x for x in backs_raw if x.get("iso_639_1") == "hi"]
    
    d = {
        "en_landscape": [IMG + "original" + x["file_path"] for x in en_backs[:BACKDROP_LIMIT]],
        "hi_landscape": [IMG + "original" + x["file_path"] for x in hi_backs[:BACKDROP_LIMIT]],
        "all_landscape": [IMG + "original" + x["file_path"] for x in backs_raw[:BACKDROP_LIMIT]],
        "all_posters": [IMG + "original" + x["file_path"] for x in posters_raw[:POSTER_LIMIT]],
        "all_logos": [IMG + "original" + x["file_path"] for x in logos_raw[:LOGO_LIMIT]],
    }
    return d


def format_links(urls):
    if not urls:
        return ""
    if len(urls) == 1:
        return urls[0]
    lines = []
    first_link = urls[0]
    for i, x in enumerate(urls[1:], 2):
        lines.append(f'{i}. <a href="{x}">HD Link</a>')
    rest = "\n".join(lines)
    return f"{first_link}\n<blockquote expandable>{rest}</blockquote>"


@app.on_message(filters.command(["p", "pc"], prefixes=["/", "!", ".", ""]))
async def poster_cmd(client, message):
    if not getattr(message, "command", None) or len(message.command) < 2:
        return await message.reply_text(
            "<b>🎬 Poster Scraper</b>\n\n"
            "<b>Usage:</b>\n"
            "<code>/p movie_name</code> - TMDB search\n"
            "<code>/p OTT_URL</code> - OTT platforms\n"
            "<code>/pc anime_name</code> - Crunchyroll search\n\n"
            "<b>Supported OTT:</b>\n"
            "Netflix, Prime Video, ZEE5, Aha, Airtel, MX Player, Crunchyroll, etc.\n\n"
            "<b>Examples:</b>\n"
            "<code>/p Spiderman</code>\n"
            "<code>/p https://zee5.com/...</code>\n"
            "<code>/pc Naruto</code>",
            parse_mode=ParseMode.HTML
        )
    
    cmd = message.command[0].lower()
    q = " ".join(message.command[1:])
    
    if cmd == "pc":
        ott_platform = "crunchyroll.com"
        cr_search = True
    else:
        ott_platform = _detect_ott_platform(q)
        cr_search = False

    if ott_platform:
        w = await message.reply_text(f"<i>📺 Fetching from {OTT_NAMES.get(ott_platform, ott_platform)}...</i>", parse_mode=ParseMode.HTML)
        ott_info = await _fetch_ott_info(q, ott_platform)
        if not ott_info:
            return await w.edit_text("<b>❌ Failed to fetch info</b>\n<i>URL/Name may be invalid or platform unavailable</i>", parse_mode=ParseMode.HTML)
        
        source = ott_info['source']
        text = f"<b>📺 {source}</b>\n\n"
        text += f"<b>🎬 Title:</b> {ott_info['title']}\n"
        if ott_info['year']:
            text += f"<b>📅 Year:</b> {ott_info['year']}\n"
        text += "\n<b>🖼 Posters:</b>\n"
        if ott_info['landscape']:
            text += f"• <a href=\"{ott_info['landscape']}\">Landscape</a>\n"
        if ott_info['poster']:
            text += f"• <a href=\"{ott_info['poster']}\">Portrait</a>\n"
        
        if not cr_search:
            text += f"\n<b>🔗 Original URL:</b>\n<code>{q}</code>"
        
        _cache_cleanup()
        cache_id = str(uuid.uuid4())[:8]
        POSTER_CACHE[cache_id] = {
            "title": ott_info['title'],
            "all_landscape": [ott_info['landscape']] if ott_info['landscape'] else [],
            "all_posters": [ott_info['poster']] if ott_info['poster'] else [],
            "ts": asyncio.get_event_loop().time()
        }
        
        buttons = []
        if ott_info['landscape']:
            buttons.append(InlineKeyboardButton("🖼 Landscape", callback_data=f"pdl_{cache_id}_land"))
        if ott_info['poster']:
            buttons.append(InlineKeyboardButton("🎬 Portrait", callback_data=f"pdl_{cache_id}_post"))
            
        keyboard = []
        if buttons:
            keyboard.append(buttons)
        
        hc_status = POSTER_CACHE[cache_id].get("hc", True)
        hc_text = "🔆 HD Enhance: ON" if hc_status else "🔅 HD Enhance: OFF"
        keyboard.append([InlineKeyboardButton(hc_text, callback_data=f"phc_{cache_id}")])
        
        return await w.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=False)
    
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
        "en_landscape": imgs["en_landscape"],
        "hi_landscape": imgs["hi_landscape"],
        "all_landscape": imgs["all_landscape"],
        "all_posters": imgs["all_posters"],
        "all_logos": imgs["all_logos"],
        "ts": asyncio.get_event_loop().time()
    }
    
    text = f"<b>Search Result</b>\n"
    text += f"<b>Query:</b> {q}\n"
    text += f"<b>Title:</b> {t}\n"
    text += f"<b>Languages:</b> {languages}\n\n"
    
    if imgs["en_landscape"]:
        en_land = format_links(imgs["en_landscape"])
        text += f"<b>English Landscape ({len(imgs['en_landscape'])} images):</b>\n{en_land}\n\n"
    
    if imgs["hi_landscape"]:
        hi_land = format_links(imgs["hi_landscape"])
        text += f"<b>Hindi Landscape ({len(imgs['hi_landscape'])} images):</b>\n{hi_land}\n\n"
    
    all_land = format_links(imgs["all_landscape"])
    posters = format_links(imgs["all_posters"])
    logos = format_links(imgs["all_logos"])
    
    text += f"<b>All Landscape ({len(imgs['all_landscape'])} images):</b>\n{all_land}\n\n"
    text += f"<b>All Posters ({len(imgs['all_posters'])} images):</b>\n{posters}\n\n"
    text += f"<b>All Logos ({len(imgs['all_logos'])} images):</b>\n{logos}\n\n"
    
    total = len(imgs["all_landscape"]) + len(imgs["all_posters"]) + len(imgs["all_logos"])
    text += f"<b>Total:</b> {total} quality links\n"
    text += f"<b>Limits:</b> Landscapes/Posters (1-40), Logos (1-15)\n\n"
    text += f"<i>Click buttons to download images:</i>"
    
    buttons = []
    if imgs["en_landscape"]:
        buttons.append(InlineKeyboardButton(f"🇬🇧 English ({len(imgs['en_landscape'])})", callback_data=f"pdl_{cache_id}_enld"))
    if imgs["hi_landscape"]:
        buttons.append(InlineKeyboardButton(f"🇮🇳 Hindi ({len(imgs['hi_landscape'])})", callback_data=f"pdl_{cache_id}_hild"))
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
    
    if img_type == "enld":
        urls = cache["en_landscape"]
        label = "English Landscape"
    elif img_type == "hild":
        urls = cache["hi_landscape"]
        label = "Hindi Landscape"
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

