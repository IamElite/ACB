import re
import asyncio
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


def _n(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


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
    p = {"query": t, "include_adult": "false", "language": "en-US", "page": 1}
    r = await _fetch_json(f"{BASE}/search/multi", params=p)
    res = r.get("results") or []
    res = [x for x in res if x.get("media_type") in ("movie", "tv")]
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
        if len(nq) <= 3:
            if nt == nq:
                sc += 1000
            elif nq in nt:
                sc += 500
        else:
            if nt == nq:
                sc += 4000
            elif nt.startswith(nq):
                sc += 2500
            elif nq in nt:
                sc += 1500
        if y and yr == y:
            sc += 5000
        sc += vc * 2
        sc += pop * 10
        if sc > best_score:
            best_score = sc
            best = (mt, x.get("id"), title, yr)
    return best


def _pick_sets(items):
    en = []
    oth = []
    nul = []
    for x in items:
        lang = x.get("iso_639_1")
        if lang == "en":
            en.append(x)
        elif lang in (None, "", "xx"):
            nul.append(x)
        else:
            oth.append(x)
    for lst in (en, oth, nul):
        lst.sort(key=lambda z: z.get("vote_count", 0), reverse=True)
    use = en or oth or nul
    return use


async def _get_images(kind, mid):
    if kind == "tv":
        url = f"{BASE}/tv/{mid}/images"
    else:
        url = f"{BASE}/movie/{mid}/images"
    r = await _fetch_json(url, params={"include_image_language": "en,null,hi,ta,te,ml,kn,bn,mr,gu,pa,ur,fr,es,de,it,ja,ko,zh"})
    d = {"posters": [], "backdrops": [], "logos": []}
    posters_raw = r.get("posters", []) or []
    backs_raw = r.get("backdrops", []) or []
    logos_raw = r.get("logos", []) or []
    use_p = _pick_sets(posters_raw)
    for x in use_p[:10]:
        d["posters"].append(IMG + "original" + x["file_path"])
    backs_raw = [x for x in backs_raw if x.get("aspect_ratio", 0) >= 1.6]
    use_b = _pick_sets(backs_raw)
    for x in use_b[:10]:
        d["backdrops"].append(IMG + "original" + x["file_path"])
    use_l = _pick_sets(logos_raw)
    for x in use_l[:10]:
        d["logos"].append(IMG + "original" + x["file_path"])
    return d


POSTER_TEMPLATE = """<b>🎬 {title}</b>

{landscape}

<b>• Logos PNG:</b>
<blockquote expandable>
{logos}
</blockquote>

<b>• Portrait Posters:</b>
<blockquote expandable>
{posters}
</blockquote>

<blockquote>Bot By ➤ @NxTalks</blockquote>"""


@app.on_message(filters.command("p"))
async def poster_cmd(client, message):
    if not getattr(message, "command", None) or len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b>\n<code>/p Movie or Series Name</code>", parse_mode=ParseMode.HTML)
    q = " ".join(message.command[1:])
    w = await message.reply_text(f"<i>Searching:</i>\n<code>{q}</code>", parse_mode=ParseMode.HTML)
    r = await _search(q)
    if not r:
        return await w.edit_text("<b>❌ Not Found</b>", parse_mode=ParseMode.HTML)
    kind, mid, title, year = r
    imgs = await _get_images(kind, mid)
    t = f"🎬 {title}"
    if year:
        t += f" ({year})"
    ls = []
    if imgs["backdrops"]:
        ls.append("<b>• English Landscape:</b>")
        for i, x in enumerate(imgs["backdrops"], 1):
            ls.append(f'{i}. <a href="{x}">Click Here</a>')
        ls.append("")
    landscape = "\n".join(ls)
    lg = []
    for i, x in enumerate(imgs["logos"], 1):
        lg.append(f'{i}. <a href="{x}">Click Here</a>')
    logos = "\n".join(lg) if lg else "No Logos Found"
    ps = []
    for i, x in enumerate(imgs["posters"], 1):
        ps.append(f'{i}. <a href="{x}">Click Here</a>')
    posters = "\n".join(ps) if ps else "No Posters Found"
    text = POSTER_TEMPLATE.format(title=t, landscape=landscape, logos=logos, posters=posters)
    await w.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=False)
