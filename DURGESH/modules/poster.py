import re
import asyncio
from difflib import SequenceMatcher
from functools import partial
from urllib.parse import quote_plus
import aiohttp
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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
    
    all_results = []
    
    p1 = {"query": t, "include_adult": "false", "language": "en-US", "page": 1}
    r1 = await _fetch_json(f"{BASE}/search/multi", params=p1)
    all_results.extend(r1.get("results") or [])
    
    p2 = {"query": t, "include_adult": "false", "language": "en-US", "page": 1}
    r2 = await _fetch_json(f"{BASE}/search/movie", params=p2)
    for x in r2.get("results") or []:
        x["media_type"] = "movie"
        all_results.append(x)
    
    p3 = {"query": t, "include_adult": "false", "language": "en-US", "page": 1}
    r3 = await _fetch_json(f"{BASE}/search/tv", params=p3)
    for x in r3.get("results") or []:
        x["media_type"] = "tv"
        all_results.append(x)
    
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


def _categorize_by_lang(items):
    en = []
    others = []
    for x in items:
        lang = x.get("iso_639_1")
        if lang == "en":
            en.append(x)
        else:
            others.append(x)
    en.sort(key=lambda z: z.get("vote_count", 0), reverse=True)
    others.sort(key=lambda z: z.get("vote_count", 0), reverse=True)
    return en, others


async def _get_images(kind, mid):
    if kind == "tv":
        url = f"{BASE}/tv/{mid}/images"
    else:
        url = f"{BASE}/movie/{mid}/images"
    r = await _fetch_json(url, params={"include_image_language": "en,null,hi,ta,te,ml,kn,bn,mr,gu,pa,ur,fr,es,de,it,ja,ko,zh,pt,ru"})
    
    posters_raw = r.get("posters", []) or []
    backs_raw = r.get("backdrops", []) or []
    logos_raw = r.get("logos", []) or []
    
    backs_raw = [x for x in backs_raw if x.get("aspect_ratio", 0) >= 1.5]
    
    en_backs, all_backs = _categorize_by_lang(backs_raw)
    all_backs = en_backs + all_backs
    
    en_posters, other_posters = _categorize_by_lang(posters_raw)
    all_posters = en_posters + other_posters
    
    en_logos, other_logos = _categorize_by_lang(logos_raw)
    all_logos = en_logos + other_logos
    
    d = {
        "en_landscape": [IMG + "original" + x["file_path"] for x in en_backs[:BACKDROP_LIMIT]],
        "all_landscape": [IMG + "original" + x["file_path"] for x in all_backs[:BACKDROP_LIMIT]],
        "all_posters": [IMG + "original" + x["file_path"] for x in all_posters[:POSTER_LIMIT]],
        "all_logos": [IMG + "original" + x["file_path"] for x in all_logos[:LOGO_LIMIT]],
    }
    return d


POSTER_TEMPLATE = """<b>Search Result</b>
<b>Query:</b> {query}
<b>Title:</b> {title}
<b>Languages:</b> English, Multiple Languages

<b>English Landscape ({en_land_count} images):</b>
<blockquote expandable>
{en_landscape}
</blockquote>

<b>All Landscape ({all_land_count} images):</b>
<blockquote expandable>
{all_landscape}
</blockquote>

<b>All Posters ({poster_count} images):</b>
<blockquote expandable>
{posters}
</blockquote>

<b>All Logos ({logo_count} images):</b>
<blockquote expandable>
{logos}
</blockquote>

<b>Total:</b> {total} quality links
<b>Limits:</b> Landscapes/Posters (1-40), Logos (1-15)"""


@app.on_message(filters.command("p"))
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
    imgs = await _get_images(kind, mid)
    
    t = f"{title}"
    if year:
        t += f" ({year})"
    
    def format_links(urls):
        if not urls:
            return "No images found"
        lines = []
        for i, x in enumerate(urls, 1):
            if i == 1:
                lines.append(x)
            else:
                lines.append(f'{i}. <a href="{x}">HD Link</a>')
        return "\n".join(lines)
    
    en_land = format_links(imgs["en_landscape"])
    all_land = format_links(imgs["all_landscape"])
    posters = format_links(imgs["all_posters"])
    logos = format_links(imgs["all_logos"])
    
    total = len(imgs["en_landscape"]) + len(imgs["all_landscape"]) + len(imgs["all_posters"]) + len(imgs["all_logos"])
    
    text = POSTER_TEMPLATE.format(
        query=q,
        title=t,
        en_landscape=en_land,
        all_landscape=all_land,
        posters=posters,
        logos=logos,
        en_land_count=len(imgs["en_landscape"]),
        all_land_count=len(imgs["all_landscape"]),
        poster_count=len(imgs["all_posters"]),
        logo_count=len(imgs["all_logos"]),
        total=total
    )
    
    await w.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
