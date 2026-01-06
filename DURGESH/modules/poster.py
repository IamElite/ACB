import asyncio, requests
from pyrogram import Client, filters
from pyrogram.types import Message
from concurrent.futures import ThreadPoolExecutor
from DURGESH import app

_ex = ThreadPoolExecutor(8)
B, I, A = "https://tmdbapi.the-zake.workers.dev/3", "https://image.tmdb.org/t/p/original", "https://graphql.anilist.co"

async def _run(f, *a):
    return await asyncio.get_running_loop().run_in_executor(_ex, f, *a)

def _tmdb(q):
    try:
        r = requests.get(f"{B}/search/multi", params={"query": q, "page": 1}, timeout=10).json()
        res = [x for x in r.get("results", []) if x.get("media_type") in ("movie", "tv")]
        if not res: return
        item = res[0]
        k, mid = item["media_type"], item["id"]
        det = requests.get(f"{B}/{k}/{mid}", timeout=10).json()
        title = det.get("title") or det.get("name") or item.get("title") or item.get("name") or "N/A"
        langs = ", ".join([l.get("english_name", "") for l in det.get("spoken_languages", [])]) or det.get("original_language", "N/A")
        imgs = requests.get(f"{B}/{k}/{mid}/images", params={"include_image_language": "en,null,hi,ja"}, timeout=10).json()
        link = lambda l, n=40: [I + x["file_path"] for x in (l or [])[:n] if x.get("file_path")]
        bk, ps, lg = imgs.get("backdrops", []), imgs.get("posters", []), imgs.get("logos", [])
        enl = [I + x["file_path"] for x in bk if x.get("iso_639_1") == "en" and x.get("file_path")]
        if not enl and item.get("backdrop_path"): enl = [I + item["backdrop_path"]]
        ap = link(ps)
        if not ap and item.get("poster_path"): ap = [I + item["poster_path"]]
        return {"t": title, "l": langs, "e": enl, "b": link(bk), "p": ap, "g": link(lg, 15)}
    except: return

def _ani(q):
    try:
        q_str = "query($s:String){Page(perPage:1){media(search:$s,type:ANIME){title{english romaji}bannerImage coverImage{extraLarge large}}}}"
        r = requests.post(A, json={"query": q_str, "variables": {"s": q}}, timeout=10).json()
        m = r.get("data", {}).get("Page", {}).get("media", [])
        if not m: return
        m = m[0]
        t = m["title"].get("english") or m["title"].get("romaji") or "N/A"
        imgs = [x for x in [m.get("bannerImage"), (m.get("coverImage") or {}).get("extraLarge"), (m.get("coverImage") or {}).get("large")] if x]
        return {"t": t, "l": "Japanese", "e": imgs[:1], "b": imgs, "p": imgs, "g": []}
    except: return

@app.on_message(filters.command("p"))
async def p_cmd(c, m: Message):
    if len(m.command) < 2: return await m.reply("**Usage:** `/p <name>`")
    query = " ".join(m.command[1:]).strip()
    status = await m.reply(f"🔍 `{query}`...")
    data = await _run(_tmdb, query)
    if not data or (not data['b'] and not data['p']): data = await _run(_ani, query)
    if not data: return await status.edit("❌")
    
    def fmt(n, s):
        if not s: return ""
        o = f"\n\n**{n} ({len(s)}):**\n"
        for i, u in enumerate(s, 1): o += f"{i}. [HD]({u})\n"
        return o

    res = f"**Result**\n**Q:** `{query}`\n**T:** `{data['t']}`\n**L:** {data['l']}"
    if data['e']: res += f"\n\n**EN Land:**\n{data['e'][0]}"
    res += fmt("Landscape", data['b']) + fmt("Posters", data['p']) + fmt("Logos", data['g'])
    res += f"\n\n**Total:** `{len(data['b']) + len(data['p']) + len(data['g'])}`"
    await status.edit(res, disable_web_page_preview=False)
