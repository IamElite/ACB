import asyncio
import requests
from pyrogram import filters
from pyrogram.errors import WebpageCurlFailed, WebpageMediaEmpty
from DURGESH import app

# AniList GraphQL Query
ANIME_QUERY = '''
query ($id: Int, $search: String) {
  Media(id: $id, search: $search, type: ANIME) {
    id
    idMal
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
    source
    averageScore
    genres
    isAdult
    siteUrl
    coverImage {
      large
    }
    bannerImage
    description
    nextAiringEpisode {
      timeUntilAiring
      episode
    }
  }
}
'''

# AniList API URL
ANILIST_API = "https://graphql.anilist.co"

# Fallback image agar koi error aaye
FAILED_PIC = "https://telegra.ph/file/09733b49f3a9d5b147d21.png"


async def fetch_anime_data(query):
    """AniList se anime data fetch karna"""
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
    """Anime info ko format karna"""
    media = data["data"]["Media"]
    
    # Basic info
    anime_id = media.get("id")
    title_rom = media["title"]["romaji"]
    title_eng = media["title"].get("english")
    title_native = media["title"]["native"]
    
    # Details
    format_type = media.get("format", "N/A")
    status = media.get("status", "N/A")
    episodes = media.get("episodes", "?")
    duration = media.get("duration")
    score = media.get("averageScore")
    genres = ", ".join(media.get("genres", []))
    site_url = media.get("siteUrl")
    
    # Image URL - AniList CDN se
    image_url = f"https://img.anili.st/media/{anime_id}"
    
    # Caption banao
    caption = f"**{title_rom}**\n"
    if title_eng:
        caption += f"__{title_eng}__\n"
    caption += f"{title_native}\n\n"
    
    caption += f"**Format:** `{format_type}`\n"
    caption += f"**Status:** `{status}`\n"
    caption += f"**Episodes:** `{episodes}`\n"
    
    if duration:
        caption += f"**Duration:** `{duration} min/ep`\n"
    
    if score:
        caption += f"**Score:** `{score}%` 🌟\n"
    
    if genres:
        caption += f"**Genres:** `{genres}`\n"
    
    caption += f"\n[View on AniList]({site_url})"
    
    return image_url, caption


@app.on_message(filters.command("anime"))
async def anime_cmd(client, message):
    """Anime search command"""
    
    # Command ke baad text check karo
    text = message.text.split(maxsplit=1)
    
    if len(text) < 2:
        await message.reply_text(
            "❌ **Query chahiye bhai!**\n\n"
            "**Example:** `/anime Naruto`"
        )
        return
    
    query = text[1]
    
    # Processing message
    process_msg = await message.reply_text("🔍 **Searching...**")
    
    try:
        # API se data fetch karo
        result = await fetch_anime_data(query)
        
        # Error check karo
        if "errors" in result:
            error_msg = result["errors"][0].get("message", "Unknown error")
            await process_msg.edit_text(f"❌ **Error:** `{error_msg}`")
            await asyncio.sleep(5)
            await process_msg.delete()
            return
        
        # Data format karo
        image_url, caption = format_anime_info(result)
        
        # Image send karo
        try:
            await message.reply_photo(
                photo=image_url,
                caption=caption
            )
            await process_msg.delete()
            
        except (WebpageMediaEmpty, WebpageCurlFailed):
            # Agar image fail ho jaye to fallback
            await message.reply_photo(
                photo=FAILED_PIC,
                caption=caption
            )
            await process_msg.delete()
    
    except Exception as e:
        await process_msg.edit_text(f"❌ **Kuch gadbad ho gayi:** `{e}`")
        await asyncio.sleep(5)
        await process_msg.delete()
