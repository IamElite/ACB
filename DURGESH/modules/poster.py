from pyrogram import Client, filters
from pyrogram.types import Message
import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor

from DURGESH import app

_executor = ThreadPoolExecutor(max_workers=4)

async def _run_sync(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, func, *args)

B = "https://tmdbapi.the-zake.workers.dev/3"
I = "https://image.tmdb.org/t/p/original"
A = "https://graphql.anilist.co"

def _tmdb_info(query):
    try:
        r = requests.get(f"{B}/search/multi", params={"query": query, "page": 1}, timeout=10).json()
        res = [x for x in r.get("results", []) if x.get("media_type") in ("movie", "tv")]
        if not res: return None
        
        item = res[0]
        k, mid = item["media_type"], item["id"]
        
        det = requests.get(f"{B}/{k}/{mid}", timeout=10).json()
        title = det.get("title") or det.get("name") or item.get("title") or item.get("name") or "N/A"
        langs = ", ".join([l.get("english_name", "") for l in det.get("spoken_languages", [])]) or det.get("original_language", "N/A")
        
        imgs = requests.get(f"{B}/{k}/{mid}/images", params={"include_image_language": "en,null,hi,ja"}, timeout=10).json()
        
        def get_urls(lst, limit=40):
            return [I + x["file_path"] for x in (lst or [])[:limit] if x.get("file_path")]

        bk, ps, lg = imgs.get("backdrops", []), imgs.get("posters", []), imgs.get("logos", [])
        en_l = [I + x["file_path"] for x in bk if x.get("iso_639_1") == "en" and x.get("file_path")]
        
        if not en_l and item.get("backdrop_path"): en_l = [I + item["backdrop_path"]]
        all_p = get_urls(ps)
        if not all_p and item.get("poster_path"): all_p = [I + item["poster_path"]]

        return {
            "title": title, "langs": langs, "en_land": en_l,
            "all_land": get_urls(bk), "all_posters": all_p, "all_logos": get_urls(lg, 15)
        }
    except: return None

def _anilist_info(query):
    try:
        q = "query($s:String){Page(perPage:1){media(search:$s,type:ANIME){title{english romaji}bannerImage coverImage{extraLarge large}}}}"
        r = requests.post(A, json={"query": q, "variables": {"s": query}}, timeout=10).json()
        m = r.get("data", {}).get("Page", {}).get("media", [])
        if not m: return None
        
        m = m[0]
        t = m["title"].get("english") or m["title"].get("romaji") or "N/A"
        imgs = [x for x in [m.get("bannerImage"), (m.get("coverImage") or {}).get("extraLarge"), (m.get("coverImage") or {}).get("large")] if x]
        
        return {
            "title": t, "langs": "Japanese (Original)", "en_land": imgs[:1],
            "all_land": imgs, "all_posters": imgs, "all_logos": []
        }
    except: return None

@app.on_message(filters.command("p"))
async def poster_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("**Usage:** `/p Movie/Anime Name`")
    
    query = " ".join(message.command[1:]).strip()
    status = await message.reply(f"🔍 Searching: `{query}`...")
    
    data = await _run_sync(_tmdb_info, query)
    if not data or (not data['all_land'] and not data['all_posters']):
        data = await _run_sync(_anilist_info, query)
    
    if not data: return await status.edit("❌ No results found!")

    def fmt(label, lst):
        if not lst: return ""
        out = f"\n\n**{label} ({len(lst)} images):**\n"
        for i, url in enumerate(lst, 1): out += f"{i}. [HD Link]({url})\n"
        return out

    msg = f"**Search Result**\n**Query:** `{query}`\n**Title:** `{data['title']}`\n**Languages:** {data['langs']}"
    if data['en_land']: msg += f"\n\n**English Landscape ({len(data['en_land'])} images):**\n{data['en_land'][0]}"
    
    msg += fmt("All Landscape", data['all_land']) + fmt("All Posters", data['all_posters']) + fmt("All Logos", data['all_logos'])
    msg += f"\n\n**Total:** `{len(data['all_land']) + len(data['all_posters']) + len(data['all_logos'])} quality links`"
    msg += f"\n**Limits:** Landscapes/Posters (1-40), Logos (1-15)"

    await status.edit(msg, disable_web_page_preview=False)
