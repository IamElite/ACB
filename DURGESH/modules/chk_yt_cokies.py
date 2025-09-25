import re
from io import StringIO
from http.cookiejar import MozillaCookieJar
from pyrogram import filters
from DURGESH import app

def parse_cookies(cookie_text):
    """Parse Netscape cookie format and validate YouTube cookies."""
    try:
        # Verify Netscape format header
        if not cookie_text.strip().startswith("# Netscape HTTP Cookie File"):
            return None
            
        cookie_jar = MozillaCookieJar()
        cookie_file = StringIO(cookie_text)
        cookie_jar._really_load(cookie_file, 'cookies.txt', True, True)
        
        # Extract YouTube cookies
        youtube_cookies = {}
        for cookie in cookie_jar:
            if 'youtube.com' in cookie.domain or '.youtube.com' in cookie.domain:
                youtube_cookies[cookie.name] = cookie.value
        
        return youtube_cookies if youtube_cookies else None
    except Exception:
        return None

def check_youtube_auth(youtube_cookies):
    """Validate YouTube authentication cookies."""
    # Check for essential authentication cookies
    has_sid = any(k.startswith('SID') for k in youtube_cookies.keys())
    has_hsid = any(k.startswith('HSID') for k in youtube_cookies.keys())
    has_ssid = any(k.startswith('SSID') for k in youtube_cookies.keys())
    has_apisid = 'APISID' in youtube_cookies
    has_sapisid = 'SAPISID' in youtube_cookies
    
    auth_cookies_present = sum([has_sid, has_hsid, has_ssid, has_apisid, has_sapisid])
    
    return {
        'authenticated': auth_cookies_present >= 3,  # At least 3 auth cookies needed
        'cookies_found': len(youtube_cookies),
        'auth_details': {
            'SID': has_sid,
            'HSID': has_hsid,
            'SSID': has_ssid,
            'APISID': has_apisid,
            'SAPISID': has_sapisid
        }
    }

@app.on_message(filters.command("chk"))
async def check_cookies(client, message):
    """Check YouTube cookies from command, reply to text, or attached document."""
    cookies_text = None
    
    # Handle different input methods
    if message.reply_to_message:
        # Reply to text message
        if message.reply_to_message.text:
            cookies_text = message.reply_to_message.text
        # Reply to document
        elif message.reply_to_message.document:
            try:
                file = await message.reply_to_message.download()
                with open(file, 'r', encoding='utf-8') as f:
                    cookies_text = f.read()
                import os
                os.remove(file)  # Clean up
            except Exception as e:
                await message.reply_text(f"Error reading document: {str(e)}")
                return
    else:
        # Direct command usage
        cookies_text = message.text.split(' ', 1)[1] if len(message.text.split()) > 1 else None
    
    if not cookies_text:
        await message.reply_text("Please provide cookies via command or reply to a message/document containing cookies.")
        return
    
    # Parse and validate cookies
    youtube_cookies = parse_cookies(cookies_text)
    if not youtube_cookies:
        await message.reply_text("❌ Invalid cookie format or no YouTube cookies found.\nExpected Netscape format with YouTube cookies.")
        return
    
    # Check authentication status
    auth_info = check_youtube_auth(youtube_cookies)
    
    status = "✅ Working" if auth_info['authenticated'] else "❌ Not Working"
    response = (
        f"**YouTube Cookie Check**\n\n"
        f"Status: {status}\n"
        f"Total Cookies: {auth_info['cookies_found']}\n\n"
        f"**Authentication Status:**\n"
    )
    
    for cookie_name, present in auth_info['auth_details'].items():
        emoji = "✅" if present else "❌"
        response += f"{emoji} {cookie_name}: {'Present' if present else 'Missing'}\n"
    
    await message.reply_text(response)
