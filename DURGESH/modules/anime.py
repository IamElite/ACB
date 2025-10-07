import asyncio
import requests
from pyrogram import filters
from pyrogram.errors import WebpageCurlFailed, WebpageMediaEmpty
from DURGESH import app

ANIME_QUERY = '''
query ($id: Int, $search: String) {
  Media(id: $id, search: $search, type: ANIME) {
    id
    title {
      romaji
      english
      native
    }
    format
    status
    episodes
    duration
    countryOfOrigin
    averageScore
    genres
    siteUrl
    coverImage {
      extraLarge
      large
    }
    studios {
      nodes {
        name
      }
    }
    tags {
      name
    }
    seasonYear
    season
  }
}
'''

ANILIST_API = "https://graphql.anilist.co"
FAILED_PIC = "https://telegra.ph/file/09733b49f3a9d5b147d21.png"


async def fetch_anime_data(query):
    variables = {"search": query} if not query.isdigit() else {"id": int(query)}
    try:
        response = requests.post(
            ANILIST_API,
            json={"query": ANIME_QUERY, "variables": variables},
            timeout=10
        )
        return response.json()
    except Exception as e:
        return {"errors": [{"message": str(e)}]}


def format_anime_info(data):
    media = data["data"]["Media"]
    
    anime_id = media.get("id")
    title_rom = media["title"]["romaji"]
    title_eng = media["title"].get("english")
    title_native = media["title"]["native"]
    
    country = media.get("countryOfOrigin", "JP")
    country_flags = {"JP": "🇯🇵", "CN": "🇨🇳", "KR": "🇰🇷"}
    c_flag = country_flags.get(country, "🌍")
    
    format_type = media.get("format", "N/A")
    status = media.get("status", "N/A")
    episodes = media.get("episodes", "?")
    duration = media.get("duration")
    score = media.get("averageScore")
    genres = ", ".join(media.get("genres", []))
    site_url = media.get("siteUrl")
    
    studios = media.get("studios", {}).get("nodes", [])
    studio_name = studios[0]["name"] if studios else "Unknown"
    
    tags = [tag["name"] for tag in media.get("tags", [])[:5]]
    tags_str = ", ".join(tags) if tags else "N/A"
    
    season = media.get("season", "")
    year = media.get("seasonYear", "")
    season_info = f"{season.title()} {year}" if season and year else ""
    
    # FIXED: Sirf coverImage use karo (poster image)
    image_url = (
        media.get("coverImage", {}).get("extraLarge") or 
        media.get("coverImage", {}).get("large") or 
        FAILED_PIC
    )
    
    if title_eng:
        caption = f"{c_flag}**{title_rom}**\n__{title_eng}__\n{title_native}\n\n"
    else:
        caption = f"{c_flag}**{title_rom}**\n{title_native}\n\n"
    
    if season_info:
        caption += f"**Season:** `{season_info} • {format_type}`\n"
    else:
        caption += f"**Format:** `{format_type}`\n"
    
    caption += f"**Status:** `{status}`"
    if episodes != "?":
        caption += f" | `{episodes} eps`"
    caption += "\n"
    
    if duration:
        caption += f"**Duration:** `{duration} min/ep`\n"
    
    if score:
        caption += f"**Score:** `{score}%` 🌟\n"
    
    caption += f"**Studio:** `{studio_name}`\n"
    
    if genres:
        caption += f"**Genres:** `{genres}`\n"
    
    if tags:
        caption += f"**Tags:** `{tags_str}`\n"
    
    caption += f"\n[View on AniList]({site_url})"
    
    return image_url, caption


@app.on_message(filters.command("anime"))
async def anime_cmd(client, message):
    text = message.text.split(maxsplit=1)
    
    if len(text) < 2:
        await message.reply_text(
            "❌ **Anime name de bhai!**\n\n"
            "**Example:** `/anime Naruto`"
        )
        return
    
    query = text[1]
    process_msg = await message.reply_text("🔍 **Searching...**")
    
    try:
        result = await fetch_anime_data(query)
        
        if "errors" in result:
            error_msg = result["errors"][0].get("message", "Unknown error")
            await process_msg.edit_text(f"❌ **Error:** `{error_msg}`")
            await asyncio.sleep(5)
            await process_msg.delete()
            return
        
        image_url, caption = format_anime_info(result)
        
        try:
            await message.reply_photo(
                photo=image_url,
                caption=caption
            )
            await process_msg.delete()
            
        except (WebpageMediaEmpty, WebpageCurlFailed, Exception) as e:
            await message.reply_photo(
                photo=FAILED_PIC,
                caption=caption
            )
            await process_msg.delete()
    
    except Exception as e:
        await process_msg.edit_text(f"❌ **Error:** `{e}`")
        await asyncio.sleep(5)
        await process_msg.delete()
