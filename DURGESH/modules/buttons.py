import re
import asyncio
import time
import logging
from typing import Dict, Optional, Tuple, List, Union

import pyrogram
from pyrogram import filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatJoinRequest
from pyrogram.enums import ParseMode, ChatType

logger = logging.getLogger("buttons")
logging.basicConfig(level=logging.INFO)

try:
    from pyrogram.enums import ButtonStyle
    RED_STYLE = ButtonStyle.DANGER
    GREEN_STYLE = ButtonStyle.SUCCESS
    BLUE_STYLE = ButtonStyle.PRIMARY
    COLOREDBUTTONSSUPPORTED = True
except (ImportError, AttributeError):
    RED_STYLE = None
    GREEN_STYLE = None
    BLUE_STYLE = None
    COLOREDBUTTONSSUPPORTED = False
    logger.warning("ButtonStyle not available - colored buttons disabled")

COLOR_MAP = {
    "r": REDSTYLE, "red": REDSTYLE, "danger": REDSTYLE, "d": REDSTYLE,
    "g": GREENSTYLE, "green": GREENSTYLE, "success": GREENSTYLE, "s": GREENSTYLE,
    "b": BLUESTYLE, "blue": BLUESTYLE, "primary": BLUESTYLE, "p": BLUESTYLE
}

from DURGESH import app
from DURGESH.database import db

authdb = db.auth_channels
btntemplatedb = db.buttontemplates

FONT_MAPS = {
    "s": (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "ᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴧʙᴄᴅєꜰɢʜɪᴊᴋʟϻησᴘǫʀꜱᴛᴜᴠᴡxʏᴢ"
    ),
    "sm": (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿"
    ),
    "sim": (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "𝖠𝖡𝖢𝖣𝖤𝖥𝖦𝖧𝖨𝖩𝖪𝖫𝖬𝖭𝖮𝖯𝖰𝖱𝖲𝖳𝖴𝖵𝖶𝖷𝖸𝖹𝖺𝖻𝖼𝖽𝖾𝖿𝗀𝗁𝗂𝗃𝗄𝗅𝗆𝗇𝗈𝗉𝗊𝗋𝗌𝗍𝗎𝗏𝗐𝗑𝗒𝗓"
    ),
    "san": (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    )
}
FONTMAPS["a"] = FONTMAPS["sim"]
FONTMAPS["b"] = FONTMAPS["san"]

REVERSE_MAP = {}
for src, dst in FONT_MAPS.values():
    for schar, dchar in zip(src, dst):
        if dchar not in REVERSEMAP:
            REVERSEMAP[dchar] = s_char

def applyfont(text: str, fontstyle: str) -> str:
    if not text or font_style == "normal":
        return text
    cleantext = "".join(REVERSEMAP.get(c, c) for c in text)
    if fontstyle in FONTMAPS:
        src, dst = FONTMAPS[fontstyle]
        table = dict(zip(src, dst))
        return "".join(table.get(c, c) for c in clean_text)
    return clean_text

URLREGEX = re.compile(r'(https?://\S+|tg://\S+|@[a-zA-Z0-9]{4,})')

def sanitizebuttonurl(url: str) -> Optional[str]:
    if not url:
        return None
    clean = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff\u00a0\r\n]+', '', url.strip().strip("'\"<>"))
    if re.match(r'^\{.*\}$', clean):
        return None
    if clean.startswith("@"):
        return f"https://t.me/{clean.lstrip('@')}"
    if customtg := re.match(r'^([a-zA-Z0-9]{4,})\.t\.me(?:/(.*))?$', clean, re.IGNORECASE):
        ch, path = customtg.group(1), customtg.group(2)
        return f"https://t.me/{ch}{'/' + path if path else ''}"
    if re.match(r'^(?:www\.)?(?:t\.me|telegram\.me|telegram\.dog)/', clean, re.IGNORECASE):
        return f"https://{clean}"
    if not clean.startswith(("http://", "https://", "tg://")):
        if re.match(r'^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}', clean):
            return f"https://{clean}"
        return None
    return clean

def create_button(text: str, url: str, style=None) -> InlineKeyboardButton:
    """Kurigram/Pyrofork compatible button creation with colored style support."""
    if style is not None and COLOREDBUTTONSSUPPORTED:
        try:
            return InlineKeyboardButton(text, url=url, style=style)
        except (TypeError, ValueError, AttributeError):
            try:
                style_val = getattr(style, "value", str(style).lower())
                return InlineKeyboardButton(text, url=url, style=style_val)
            except Exception:
                pass
    return InlineKeyboardButton(text, url=url)

BUTTON_REGEX = re.compile(r'\[([^\]]+)\](?:\s[:\-–—|]?\s\[?\(?([a-zA-Z]+)\)?\]?)?')

def parsebuttons(text: str, fontstyle: str = "sim", defaultcolor=REDSTYLE) -> Optional[InlineKeyboardMarkup]:
    if not text:
        return None

    raw_lines = text.strip().splitlines()
    keyboard = []

    for line in raw_lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        row = []
        for content, outcolor in BUTTONREGEX.findall(line_clean):
            colorsuffix = (outcolor or "").strip().lower()

            match = URL_REGEX.search(content)
            if match:
                label = re.sub(r'[\s+|:–—\->]+$', '', content[:match.start()]).strip()
                raw_url = match.group(1).strip()
                in_color = re.sub(r'^[\s+|:–—\->]+', '', content[match.end():]).strip().lower()
            else:
                parts = re.split(r'\s+(?:\+|\->|\|)\s+', content)
                if len(parts)  2 else ""

            if not label or not (cleanurl := sanitizebuttonurl(rawurl)):
                continue

            btncolor = COLORMAP.get(incolor or colorsuffix, default_color)
            styledtext = applyfont(label, fontstyle) if fontstyle != "normal" else label
            row.append(createbutton(styledtext, cleanurl, style=btncolor))

        if row:
            keyboard.append(row)

    return InlineKeyboardMarkup(keyboard) if keyboard else None

def parsetimetoseconds(timestr: str) -> int:
    if not time_str:
        return 1
    if match := re.match(r'^(\d+)([smhd])$', time_str.strip().lower()):
        return int(match.group(1)) * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}.get(match.group(2), 1)
    return 1

async def addauthchannel(chatid: int, forwardtag: bool = True, autoaccepttime: str = "1s", admin_id: Optional[int] = None):
    cidstr = str(chatid)
    payload = {
        "chatid": cidstr,
        "forwardtagremoval": forward_tag,
        "autoaccepttime": autoaccepttime,
        "autoacceptseconds": parsetimetoseconds(autoaccept_time)
    }
    if admin_id:
        payload["adminid"] = str(adminid)
    await authdb.update_one(
        {"$or": [{"chatid": cidstr}, {"chatid": chatid}]},
        {"$set": payload},
        upsert=True
    )

async def removeauthchannel(chat_id: int):
    cidstr = str(chatid)
    await authdb.deletemany({"$or": [{"chatid": cidstr}, {"chatid": chat_id}]})

async def getchannelsettings(chat_id: int, username: Optional[str] = None) -> Optional[Dict]:
    cidstr = str(chatid)
    rawnum = cidstr.replace("-100", "").replace("-", "")
    queries = [{"chatid": cidstr}]
    try:
        queries.append({"chatid": int(cidstr)})
    except Exception:
        pass
    if raw_num.isdigit():
        queries.extend([
            {"chatid": rawnum},
            {"chatid": int(rawnum)},
            {"chatid": f"-100{rawnum}"},
            {"chatid": int(f"-100{rawnum}")}
        ])
    if username:
        u = username.lstrip("@").lower()
        queries.extend([{"chatid": f"@{u}"}, {"chatid": u}])

    if data := await authdb.find_one({"$or": queries}):
        return {
            "chatid": data.get("chatid"),
            "forwardtagremoval": data.get("forwardtagremoval", True),
            "autoaccepttime": data.get("autoaccepttime", "1s"),
            "autoacceptseconds": data.get("autoacceptseconds", 1),
            "adminid": data.get("adminid")
        }
    return None

async def ischannelauthed(chat_id: int, username: Optional[str] = None) -> bool:
    return bool(await getchannelsettings(chat_id, username))

async def savebuttontemplate(userid: int, template: str, fontstyle: str = "sim"):
    uidstr = str(userid)
    now = time.time()
    await btntemplatedb.updateone(
        {"$or": [{"userid": uidstr}, {"userid": userid}]},
        {"$set": {"userid": uidstr, "template": template, "fontstyle": fontstyle, "updated_at": now}},
        upsert=True
    )
    await btntemplatedb.updateone(
        {"id": "GLOBALACTIVE_TEMPLATE"},
        {"$set": {"template": template, "fontstyle": fontstyle, "updatedat": now, "adminid": uid_str}},
        upsert=True
    )
    try:
        await authdb.update_many(
            {"$or": [{"adminid": {"$exists": False}}, {"adminid": None}, {"admin_id": ""}]},
            {"$set": {"adminid": uidstr}}
        )
    except Exception:
        pass

async def getbuttontemplate(user_id: int) -> Optional[Dict]:
    uidstr = str(userid)
    return await btntemplatedb.findone({"$or": [{"userid": uidstr}, {"userid": userid}]})

async def geteffectivetemplate(chat_id: int, username: Optional[str] = None) -> Optional[Dict]:
    settings = await getchannelsettings(chat_id, username)
    if settings and settings.get("admin_id"):
        if tmpl := await getbuttontemplate(settings["admin_id"]):
            if tmpl.get("template"):
                return tmpl

    if globaltmpl := await btntemplatedb.findone({"id": "GLOBALACTIVETEMPLATE"}):
        if global_tmpl.get("template"):
            return global_tmpl

    return await btntemplatedb.findone(
        {"template": {"$exists": True, "$ne": ""}},
        sort=[("updatedat", -1), ("id", -1)]
    )

async def deletebuttontemplate(user_id: int):
    uidstr = str(userid)
    await btntemplatedb.deletemany({"$or": [{"userid": uidstr}, {"userid": userid}]})

def getforwardchat(msg: Optional[Message]):
    if not msg:
        return None
    origin = getattr(msg, "forward_origin", None)
    if origin:
        chat = getattr(origin, "chat", None)
        if chat:
            return getattr(chat, "sender_chat", chat)
        sender = getattr(origin, "sender_chat", None)
        if sender:
            return sender
    if not hasattr(msg, "forward_origin"):
        try:
            return getattr(msg, "forwardfromchat", None)
        except Exception:
            return None
    return None

def isforwardedpost(msg: Message) -> bool:
    if getattr(msg, "forward_origin", None) is not None:
        return True
    return bool(getattr(msg, "forward_date", None))

def extractchatandmsgid(link: str) -> Tuple[Optional[int], Optional[int]]:
    if priv := re.match(r"https?://t\.me/c/(-?\d+)/(\d+)", link.strip()):
        raw = priv.group(1).lstrip("-")
        return (int(f"-{raw}") if raw.startswith("100") else int(f"-100{raw}")), int(priv.group(2))
    return None, None

def entityname(entity_type) -> str:
    if hasattr(entity_type, "name"):
        return str(entity_type.name).upper()
    val = getattr(entitytype, "value", entitytype)
    if isinstance(val, str):
        return val.upper()
    if hasattr(val, "name"):
        return val.name.upper()
    return str(val).upper()

ENTITY_TAGS = {
    "BOLD": ("", ""),
    "ITALIC": ("", ""),
    "CODE": ("", ""),
    "STRIKETHROUGH": ("", ""),
    "UNDERLINE": ("", ""),
    "SPOILER": ("", ""),
    "BLOCKQUOTE": ("", ""),
    "EXPANDABLE_BLOCKQUOTE": ("", "")
}

def gethtmltext(text: str, entities: list) -> str:
    if not text or not entities:
        return text or ""
    try:
        text_16 = text.encode('utf-16-le')
    except Exception:
        return text

    events = {}
    for i, e in enumerate(entities):
        start = e.offset * 2
        end = (e.offset + e.length) * 2
        tname = entity_name(e.type)

        starttag, endtag = ENTITYTAGS.get(tname, ("", ""))
        if not start_tag:
            if "PRE" in t_name:
                lang = getattr(e, "language", "") or ""
                starttag, endtag = f'', ""
            elif "TEXTLINK" in tname and hasattr(e, "url"):
                starttag, endtag = f'', ""
            elif "TEXTMENTION" in tname and hasattr(e, "user") and e.user:
                starttag, endtag = f'', ""

        if start_tag:
            events.setdefault(start, []).append(('start', i, start_tag))
            events.setdefault(end, []).append(('end', i, end_tag))

    res = ""
    last_idx = 0
    for idx in sorted(events.keys()):
        res += text16[lastidx:idx].decode('utf-16-le')
        evs = events[idx]
        for e in sorted([x for x in evs if x[0] == 'end'], key=lambda x: x[1], reverse=True):
            res += e[2]
        for e in sorted([x for x in evs if x[0] == 'start'], key=lambda x: x[1]):
            res += e[2]
        last_idx = idx

    res += text16[lastidx:].decode('utf-16-le')
    return res

TRIGGERHTMLREGEX = re.compile(
    r'(?:^|\n|\s)[-–—•▪►👉🔗~]+\s]?\s+)?href="\'["\'][^>]>.?',
    re.IGNORECASE
)
TRIGGERPLAINREGEX = re.compile(
    r'(?:^|\n|\s)[-–—•▪►👉🔗~]+\s*(https?://[^\s<>"\']+|tg://[^\s<>"\']+|t\.me/[^\s<>"\']+)',
    re.IGNORECASE
)

def extracttriggerlinkandcleancaption(rawtext: str, html_text: str) -> Tuple[Optional[str], str, str]:
    if not rawtext and not htmltext:
        return None, "", ""
    targettext = htmltext or raw_text

    if mhtml := TRIGGERHTMLREGEX.search(targettext):
        url = m_html.group(1).strip()
        clhtml = TRIGGERHTMLREGEX.sub('', targettext).strip()
        clraw = TRIGGERHTMLREGEX.sub('', rawtext).strip() if rawtext else clhtml
        return url, clraw, clhtml

    if mplain := TRIGGERPLAINREGEX.search(targettext):
        url = m_plain.group(1).strip()
        clhtml = TRIGGERPLAINREGEX.sub('', targettext).strip()
        clraw = TRIGGERPLAINREGEX.sub('', rawtext).strip() if rawtext else clhtml
        return url, clraw, clhtml

    return None, rawtext, htmltext

def applyfonttocaption(caption: str, fontstyle: str) -> str:
    if not caption or font_style == "normal":
        return hyperlinksyntaxrealm(caption)
    
    pattern = re.compile(r'(]+>|https?://[^\s]+|t\.me/[^\s]+|tg://[^\s]+)')
    lines = []
    for line in caption.split('\n'):
        lower_line = line.lower()
        if "syntaxrealm" in lowerline or "made by" in lowerline:
            lines.append(line)
            continue

        parts = pattern.split(line)
        styled = [p if (p.startswith('')) or p.startswith(('http', 't.me', 'tg://')) else applyfont(p, fontstyle) for p in parts if p]
        lines.append(''.join(styled))
    
    formatted_caption = '\n'.join(lines)
    return hyperlinksyntaxrealm(formatted_caption)

def hyperlinksyntaxrealm(text: str) -> str:
    if not text:
        return text

    if 'href="https://t.me/SyntaxRealm"' in text:
        return text

    credit_link = '˹ 𝖲𝗒𝗇𝗍𝖺𝖷𝖱𝖾𝖺𝗅𝗆.𝗍.𝗆𝖾 ˼'
    credit_pattern = re.compile(
        r"['\"]?\s(?:˹\s)?SyntaxRealm(?:\.t\.me)?(?:\s˼)?\s['\"]?",
        re.IGNORECASE
    )
    return creditpattern.sub(creditlink, text)

async def safecopyand_delete(
    msg: Message,
    chat_id: int,
    caption: Optional[str] = None,
    reply_markup: Optional[InlineKeyboardMarkup] = None
) -> Optional[Message]:
    markup = replymarkup if replymarkup is not None else msg.reply_markup
    for _ in range(5):
        try:
            if msg.media:
                c = caption if caption is not None else (msg.caption or "")
                sent = await msg.copy(
                    chat_id,
                    caption=c,
                    parse_mode=ParseMode.HTML if caption else None,
                    reply_markup=markup
                )
            else:
                t = caption if caption is not None else (msg.text or "")
                sent = await app.send_message(
                    chatid=chatid,
                    text=t,
                    parse_mode=ParseMode.HTML if caption else None,
                    reply_markup=markup,
                    disablewebpage_preview=False
                )
            await asyncio.sleep(0.4)
            await msg.delete()
            return sent
        except Exception as e:
            if "FLOOD_WAIT" in str(e).upper():
                wait_match = re.search(r'(\d+)', str(e))
                waitsec = int(waitmatch.group(1)) + 2 if wait_match else 5
                await asyncio.sleep(wait_sec)
                continue
            logger.error(f"[AUTO-BUTTON] safecopyand_delete failed: {e}")
            break
    return None

def ischannelchat(chat) -> bool:
    """Kurigram/Pyrogram compatible channel check."""
    if not chat:
        return False
    chat_type = getattr(chat, "type", None)
    if chat_type is None:
        return False
    # Check both enum and string
    if chat_type == ChatType.CHANNEL:
        return True
    if hasattr(chattype, "value") and chattype.value == "channel":
        return True
    if str(chat_type).lower() in ["channel", "chatchype.channel"]:
        return True
    return False

@app.on_message(filters.command(["auth"]))
async def auth_cmd(client, message: Message):
    args = message.text.split()
    forward_tag = "-f" in args and args[args.index("-f") + 1].lower() in ["on", "true", "1"] if "-f" in args and args.index("-f") + 1 = 2:
        try:
            chatid = (await client.getchat(args[1])).id if args[1].startswith("@") else int(args[1])
        except Exception as e:
            return await message.reply_text(f"❌ Invalid channel! Error: {e}")

    if not chat_id:
        return await message.replytext("❌ Usage: /auth  -f on/off -ac 1s")

    try:
        chatobj = await client.getchat(chat_id)
        if not ischannelchat(chat_obj):
            return await message.reply_text("❌ Ye sirf channels ke liye hai! Groups/supergroups ke liye kaam nahi karega.")
    except Exception as e:
        return await message.reply_text(f"❌ Channel verify nahi ho paya: {e}")

    adminid = message.fromuser.id if message.from_user else None
    await addauthchannel(chatid, forwardtag, autoaccept, adminid=admin_id)
    await message.reply_text(
        f"✅ Channel Authorized!\n🆔 {chatid}\n🔄 Forward Tag Removal: {'ON' if forwardtag else 'OFF'}\n⏱ Auto-Accept: {auto_accept}"
    )

@app.on_message(filters.command(["unauth"]))
async def unauth_cmd(client, message: Message):
    chat_id = None
    if len(message.command) >= 2:
        try:
            chatid = (await client.getchat(message.command[1])).id if message.command[1].startswith("@") else int(message.command[1])
        except Exception:
            return await message.reply_text("❌ Invalid channel!")
    elif fwd := getforwardchat(message.replytomessage):
        chat_id = fwd.id

    if not chat_id:
        return await message.replytext("❌ Usage: /unauth ")

    await removeauthchannel(chat_id)
    await message.replytext(f"✅ Un-Authorized: {chatid}")

@app.on_message(filters.command(["abset", "absee", "abseen", "abrm"]))
async def templatemgmthandler(client, message: Message):
    cmd = message.command[0].lower()
    userid = message.fromuser.id if message.from_user else 0

    if cmd == "abrm":
        await deletebuttontemplate(user_id)
        return await message.reply_text("🗑️ Template remove kar diya gaya hai!")

    if cmd in ["absee", "abseen"]:
        data = await getbuttontemplate(userid) or await btntemplatedb.findone({"id": "GLOBALACTIVETEMPLATE"})
        if not data:
            return await message.reply_text("❌ Koi template set nahi hai! Pehle /abset karein.")
        preview_text = data["template"].replace("{link}", "https://t.me/PreviewDemo")
        previewkeyboard = parsebuttons(previewtext, fontstyle=data.get("fontstyle", "sim"), defaultcolor=RED_STYLE)
        return await message.reply_text(
            f"📋 Aapka Button Template:\n{data['template']}\n\n🎨 Font: {data.get('font_style', 'sim')}\n👇 Button Preview:",
            replymarkup=previewkeyboard
        )

    if cmd == "abset":
        text = message.text or message.caption or ""
        font_style = "sim"
        if font_match := re.search(r"-f\s+(\w+)", text):
            fontstyle = fontmatch.group(1).lower()

        template_text = ""
        if message.replytomessage and (message.replytomessage.text or message.replytomessage.caption):
            templatetext = message.replytomessage.text or message.replyto_message.caption
        else:
            template_text = re.sub(r"^/abset\s*", "", text, flags=re.IGNORECASE)
            templatetext = re.sub(r"-f\s+\w+", "", templatetext, flags=re.IGNORECASE).strip()

        if not template_text:
            return await message.reply_text("❌ Template text provide karein! Format: /abset [Text + {link}]")

        testtext = re.sub(r"\{\s*(?:link|url|target)\s*\}", "https://t.me/PreviewDemo", templatetext, flags=re.IGNORECASE)
        testkeyboard = parsebuttons(testtext, fontstyle=fontstyle, defaultcolor=RED_STYLE)
        if not test_keyboard:
            return await message.reply_text("❌ Koi valid button nahi mila! Please check your bracket format.")

        await savebuttontemplate(userid, templatetext, font_style)
        return await message.reply_text(
            f"✅ Button Template Set Ho Gaya!\n🎨 Font: {font_style}\n🔴 Default Color: Danger (Red)\n👇 Live Preview:",
            replymarkup=testkeyboard
        )

@app.on_message(filters.command(["ab"]))
async def manualabcmd(client, message: Message):
    args = message.command[1:]
    if not args:
        return await message.replytext("❌ Usage: /ab ")

    target_link = args[0]
    channelid, msgid = extractchatandmsgid(target_link)
    if not channel_id:
        if pub := re.match(r"https?://t\.me/([a-zA-Z0-9]{5,})/(\d+)", targetlink):
            try:
                channelid, msgid = (await client.get_chat(pub.group(1))).id, int(pub.group(2))
            except Exception as e:
                return await message.reply_text(f"❌ Channel nahi mila: {e}")
        else:
            return await message.reply_text("❌ Invalid post link format!")

    replacement_link = None
    if message.replytomessage:
        repliedtext = message.replytomessage.text or message.replyto_message.caption or ""
        if m := re.search(r"(https?://\S+)", replied_text):
            replacement_link = m.group(1)

    templatedata = await getbuttontemplate(message.fromuser.id) or await geteffectivetemplate(channel_id)
    if not template_data:
        return await message.reply_text("❌ Pehle /abset se template set karein!")

    template = template_data["template"]
    fontstyle = templatedata.get("font_style", "sim")

    try:
        targetmsg = await client.getmessages(channelid, msgid)
        originaltext = targetmsg.caption or target_msg.text or ""
        originalentities = targetmsg.captionentities or targetmsg.entities

        if not replacement_link:
            htmltext = gethtmltext(originaltext, original_entities)
            exturl, clraw, clhtml = extracttriggerlinkandcleancaption(originaltext, htmltext)
            if ext_url:
                replacementlink = exturl
                originaltext = clhtml
                original_entities = []

        if not replacement_link and "{link}" in template.lower():
            return await message.reply_text("❌ Replacement link nahi mila! Link reply karein ya post me -link dalein.")

        btnstr = re.sub(r"\{\s*(?:link|url|target)\s*\}", replacementlink or "", template, flags=re.IGNORECASE)
        keyboard = parsebuttons(btnstr, fontstyle=fontstyle, defaultcolor=REDSTYLE)
        if not keyboard:
            return await message.reply_text("❌ Buttons parse nahi ho paye.")

        formattedcaption = applyfonttocaption(originaltext, fontstyle) if fontstyle != "normal" else originaltext

        try:
            if target_msg.media:
                await client.editmessagecaption(channelid, msgid, caption=formattedcaption, parsemode=ParseMode.HTML, reply_markup=keyboard)
            else:
                await client.editmessagetext(text=formattedcaption, chatid=channelid, messageid=msgid, parsemode=ParseMode.HTML, reply_markup=keyboard)
        except Exception as edit_err:
            if "MESSAGENOTMODIFIED" in str(edit_err).upper():
                await client.editmessagereplymarkup(chatid=channelid, messageid=msgid, replymarkup=keyboard)
            else:
                raise

        await message.reply_text("✅ Buttons Successfully Attached!")
    except Exception as e:
        if "MESSAGENOTMODIFIED" in str(e).upper():
            await message.reply_text("ℹ️ Post pehle se updated hai!")
        else:
            await message.reply_text(f"⚠️ Edit fail: {e}")

@app.on_message(filters.command(["cb"]))
async def changebuttonscmd(client, message: Message):
    if not message.replytomessage or not (message.replytomessage.text or message.replytomessage.caption):
        return await message.replytext("❌ Reply to a button-template message with /cb ")
    if len(message.command) ")

    link = message.command[1]
    channelid, msgid = extractchatandmsgid(link)
    if not channel_id:
        if pub := re.match(r"https?://t\.me/([a-zA-Z0-9_]{5,})/(\d+)", link):
            try:
                channelid, msgid = (await client.get_chat(pub.group(1))).id, int(pub.group(2))
            except Exception as e:
                return await message.reply_text(f"❌ Channel error: {e}")
        else:
            return await message.reply_text("❌ Invalid link format!")

    rawbtn = message.replytomessage.text or message.replyto_message.caption
    keyboard = parsebuttons(rawbtn, fontstyle="normal", defaultcolor=RED_STYLE)
    if not keyboard:
        return await message.reply_text("❌ Invalid button layout!")

    try:
        await client.editmessagereplymarkup(chatid=channelid, messageid=msgid, replymarkup=keyboard)
        await message.reply_text("✅ Buttons updated successfully!")
    except Exception as e:
        await message.reply_text(f"⚠️ Update error: {e}")

async def dispatchchannelpost(client, message: Message):
    # 🔒 STRICT CHANNEL CHECK - Kurigram compatible
    if not ischannelchat(message.chat):
        logger.debug(f"Skipping non-channel chat: {message.chat.id} (type: {message.chat.type})")
        return

    chat_id = message.chat.id
    raw_text = message.caption or message.text or ""
    if not raw_text:
        return

    entities = message.caption_entities or message.entities
    htmltext = gethtmltext(rawtext, entities)
    extractedurl, clraw, clhtml = extracttriggerlinkandcleancaption(rawtext, htmltext)

    settings = await getchannelsettings(chat_id, message.chat.username)

    if not extracted_url:
        if settings and settings.get("forwardtagremoval") and isforwardedpost(message):
            await safecopyanddelete(message, chatid)
        return

    if not settings:
        settings = {
            "chatid": str(chatid),
            "forwardtagremoval": True,
            "autoaccepttime": "1s",
            "autoacceptseconds": 1
        }
        asyncio.createtask(addauthchannel(chatid, forwardtag=True, autoaccept_time="1s"))

    tmpldata = await geteffectivetemplate(chatid, message.chat.username)
    if not tmpldata or not tmpldata.get("template"):
        return

    fontstyle = tmpldata.get("font_style", "sim")
    btntext = tmpldata.get("template", "")
    btntext = re.sub(r"\{\s*(?:link|url|target)\s*\}", extractedurl, btn_text, flags=re.IGNORECASE)

    keyboard = parsebuttons(btntext, fontstyle=fontstyle, defaultcolor=REDSTYLE)
    if not keyboard:
        return

    finalcaption = applyfonttocaption(clhtml, fontstyle) if fontstyle != "normal" else clhtml
    rawcaption = applyfonttocaption(clraw, fontstyle) if fontstyle != "normal" else clraw

    if settings.get("forwardtagremoval", True) and isforwardedpost(message):
        await safecopyanddelete(message, chatid, caption=finalcaption, replymarkup=keyboard)
        return

    edit_success = False
    try:
        if message.media:
            await client.editmessagecaption(
                chatid=chatid,
                message_id=message.id,
                caption=final_caption,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await client.editmessagetext(
                text=final_caption,
                chatid=chatid,
                message_id=message.id,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        edit_success = True
    except Exception as err:
        err_str = str(err).upper()
        logger.warning(f"First edit attempt failed: {err}")
        if "MESSAGENOTMODIFIED" in err_str:
            try:
                await client.editmessagereplymarkup(chatid=chatid, messageid=message.id, reply_markup=keyboard)
                edit_success = True
            except Exception:
                pass
        else:
            try:
                if message.media:
                    await client.editmessagecaption(
                        chatid=chatid,
                        message_id=message.id,
                        caption=raw_caption,
                        parse_mode=None,
                        reply_markup=keyboard
                    )
                else:
                    await client.editmessagetext(
                        text=raw_caption,
                        chatid=chatid,
                        message_id=message.id,
                        parse_mode=None,
                        reply_markup=keyboard
                    )
                edit_success = True
            except Exception:
                pass

    if not edit_success:
        await safecopyanddelete(message, chatid, caption=finalcaption, replymarkup=keyboard)

# 🔒 SIRF CHANNELS KE LIYE - Groups hata diye
@app.on_message(filters.channel & ~filters.service)
async def channelpostlistener(client, message: Message):
    await dispatchchannelpost(client, message)

@app.oneditedmessage(filters.channel & ~filters.service)
async def channelpostedit_listener(client, message: Message):
    await dispatchchannelpost(client, message)

@app.onchatjoin_request()
async def autoapprovejoin_request(client, request: ChatJoinRequest):
    try:
        if settings := await getchannelsettings(request.chat.id):
            await asyncio.sleep(settings.get("autoacceptseconds", 1))
            await client.approvechatjoinrequest(chatid=request.chat.id, userid=request.fromuser.id)
    except Exception as e:
        logger.error(f"Auto-approve join request failed: {e}")

Agar abhi bhi channel par kaam nahi kar raha, toh Koyeb logs bhejo - main dekh lunga kya issue hai! 🚀
