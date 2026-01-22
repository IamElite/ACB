import re
from bs4 import BeautifulSoup
import asyncio
from curl_cffi import requests
from pyrogram import filters
from DURGESH import app

# curl_cffi handles TLS/Headers. We just need to impersonate.

def get_njav_data(jav_id):
    jav_id = jav_id.strip()
    url = f"https://njavtv.com/en/{jav_id.lower()}"
    data = {
        "id": jav_id.upper(),
        "model": "Unknown",
        "studio": "Unknown",
        "duration": "Unknown",
        "playlist": None
    }
    
    try:
        # Masquerade as Safari to bypass WAF (tested on Colab)
        response = requests.get(url, impersonate="safari15_5", timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Targeted UUID search (nineyu or surrit)
            # Looks for: nineyu.com/UUID or surrit.com/UUID (handling escaped slashes)
            domain_uuids = re.findall(r'(?:surrit|nineyu)\.com(?:\\/|/)([a-f0-9-]{36})', response.text)
            
            if domain_uuids:
                data["playlist"] = f"https://surrit.com/{domain_uuids[0]}/playlist.m3u8"
            else:
                uuids = re.findall(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', response.text)
                if uuids:
                    for uuid in uuids:
                        if "user_uuid" not in response.text[response.text.find(uuid)-20:response.text.find(uuid)]:
                            data["playlist"] = f"https://surrit.com/{uuid}/playlist.m3u8"
                            break
            
            actor_meta = soup.find("meta", property="og:video:actor")
            if actor_meta:
                data["model"] = actor_meta.get("content", "Unknown")
            else:
                actress_links = soup.select('a[href*="/actress/"]')
                if actress_links:
                    data["model"] = ", ".join([a.get_text(strip=True) for a in actress_links])

            duration_meta = soup.find("meta", property="og:video:duration")
            if duration_meta:
                try:
                    total_seconds = int(duration_meta.get("content", 0))
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    data["duration"] = f"{hours}h {minutes}m {seconds}s"
                except ValueError:
                    pass
            
            if data["duration"] == "Unknown":
                for label in soup.find_all(string=re.compile(r'(Duration|Runtime|Time)', re.I)):
                    parent = label.parent
                    full_text = parent.get_text(strip=True)
                    if ":" in full_text:
                        data["duration"] = full_text.split(":", 1)[1].strip()
                        break
                    sib_el = parent.find_next_sibling('span') or parent.find_next_sibling('div')
                    if sib_el:
                         data["duration"] = sib_el.get_text(strip=True)
                         break
                    sib_el = parent.find_next_sibling('span') or parent.find_next_sibling('div')
                    if sib_el:
                        data["duration"] = sib_el.get_text(strip=True)
                        break

            found_studio = False
            for label in soup.find_all(string=re.compile(r'(Maker|Label|Studio)', re.I)):
                parent = label.parent
                value_node = parent.find_next_sibling('a') or parent.find_next_sibling('span')
                if value_node:
                    data["studio"] = value_node.get_text(strip=True)
                    found_studio = True
                    break 
                full_text = parent.get_text(strip=True)
                if ":" in full_text:
                    data["studio"] = full_text.split(":", 1)[1].strip()
                    found_studio = True
                    break
            
            if not found_studio or data["studio"] == "Unknown":
                keywords_meta = soup.find("meta", attrs={"name": "keywords"})
                if keywords_meta:
                    content = keywords_meta.get("content", "")
                    if content:
                        parts = [p.strip() for p in content.split(",") if p.strip()]
                        if parts:
                            data["studio"] = parts[-1]
            
    except Exception as e:
        data["studio"] = f"Error: {e}"
        data["model"] = f"Err: {type(e).__name__}"
        
    return data

def get_4ktwo_thumb(jav_id):
    search_url = f"https://4ktwo.net/search.php?mod=forum&searchsubmit=yes&srchtxt={jav_id}"
    try:
        # 4ktwo might not need advanced impersonation, but keeping consistent is safe
        # Or simple requests might be fine. Let's use curl_cffi for consistency.
        resp = requests.get(search_url, impersonate="safari15_5", timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        if "searchid" not in resp.url and "searchid" not in search_url:
             pass

        thread_link = None
        
        for a in soup.select('.xs3 a'):
            if jav_id.replace('-', '').lower() in a.get_text().replace('-', '').lower() or jav_id.lower() in a.get_text().lower():
                thread_link = a['href']
                break
        
        if not thread_link:
             for a in soup.select('.xst'):
                if jav_id.replace('-', '').lower() in a.get_text().replace('-', '').lower() or jav_id.lower() in a.get_text().lower():
                    thread_link = a['href']
                    break
                    
        if not thread_link:
             for a in soup.find_all('a', href=True):
                 if "thread" in a['href'] and jav_id.lower() in a.get_text().lower():
                     thread_link = a['href']
                     break

        if thread_link:
            if not thread_link.startswith('http'):
                thread_link = "https://4ktwo.net/" + thread_link
            
            thread_resp = requests.get(thread_link, impersonate="safari15_5", timeout=15)
            thread_soup = BeautifulSoup(thread_resp.text, 'html.parser')
            
            post_content = thread_soup.find('div', class_='pcb')
            if not post_content:
                 post_content = thread_soup.find('td', class_='t_f')
            
            if post_content:
                images = post_content.find_all('img', class_='zoom')
                if not images:
                    images = post_content.find_all('img')

                for img in images:
                    src = img.get('zoomfile') or img.get('file') or img.get('src')
                    if src and src.startswith('http'):
                        if any(x in src for x in ['logo', 'avatar', 'gif', 'icon', 'smile']):
                            pass
                        else:
                            if any(src.lower().endswith(ext) for ext in ['.jpg', '.png', '.jpeg']):
                                return src
                            
            for img in thread_soup.find_all('img'):
                src = img.get('zoomfile') or img.get('file') or img.get('src')
                if src and src.startswith('http') and "bocecdn" in src:
                    return src 

    except Exception:
        pass
    return None

@app.on_message(filters.command(["jav", "j"], prefixes=["/", "!", ".", ""]))
async def jav_search_cmd(client, message):
    if len(message.command) < 2:
        await message.reply_text("**Usage:**\n`/jav <code>`\n`jav <code>`\n\n**Example:**\n`jav IPZZ-771`")
        return

    jav_code = message.text.split(maxsplit=1)[1] if len(message.command) > 1 else None
    if not jav_code:
         jav_code = message.command[1]

    status_msg = await message.reply_text(f"🔎 Searching for `{jav_code}`...", quote=True)

    try:
        loop = asyncio.get_running_loop()
        
        njav_data = await loop.run_in_executor(None, get_njav_data, jav_code)
        thumb_url = await loop.run_in_executor(None, get_4ktwo_thumb, jav_code)

        caption = (
            f"👀 **ID** - `{njav_data['id']}`\n"
            f"😋 **MODEL** - {njav_data['model']}\n"
            f"✨ **STUDIO** - {njav_data['studio']}\n"
            f"⌛️ **DURATION** - {njav_data['duration']}\n\n"
        )
        
        if njav_data['playlist']:
            caption += f"**STREAM LINK -**\n{njav_data['playlist']}"
        else:
             caption += "**STREAM LINK -**\n❌ Not Found"

        if thumb_url:
            await message.reply_photo(
                photo=thumb_url,
                caption=caption,
                quote=True
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text(caption, disable_web_page_preview=True)

    except Exception as e:
        await status_msg.edit_text(f"⚠️ **Error:** {str(e)}")
