import asyncio
import hashlib
import html
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

from pyrogram import filters, raw, types, enums, errors
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo, InputMediaAnimation,
    InputMediaAudio, InputMediaDocument, LinkPreviewOptions,
)

from config import OWNER_ID, ADMINS
from DURGESH import app
from DURGESH.database import db

_cfgdb = db.clone_config
_chatsdb = db.clone_chats
_mapdb = db.clone_mapping
_adminsdb = db.clone_admins
_promodb = db.apauth_channels

HANDLER_GROUP = 11
CACHE_MAX = 5000
ALBUM_WINDOW = 1.5
EDIT_DEBOUNCE = 0.5
BULK_WINDOW = 60
WIPE_CHUNK = 100
WIPE_CONCURRENCY = 3
WIPE_SLEEP = (0.4, 0.7)
VAL_CONCURRENCY = 6
BIO_POLL = 30
ALBUM_MAP_MAX = 1000
DEDUP_TTL = 30
RECENT_SELF_HOURS = 12
TTL_DAYS = 30

_MAIN: Optional[int] = None
_SUBS: set[int] = set()
_ENABLED = False
_PROTECT = True
_WIPE_PROMO_PROTECT = True
_WIPE_RECENT_HOURS = RECENT_SELF_HOURS
_WIPE_BOOT = False
_BIO_CLONE = True
_CLONE_ADMINS: set[int] = set()
_CACHE: Dict[Tuple[int, int], Dict[str, Any]] = {}
_CACHE_KEYS: list[Tuple[int, int]] = []
_ALBUM_BUF: Dict[str, Dict[str, Any]] = {}
_EDIT_TASKS: Dict[Tuple[int, int], Tuple[asyncio.Task, float]] = {}
_BULK_SESS: Dict[int, Dict[str, Any]] = {}
_PROMO_WHITELIST: Dict[int, set[int]] = {}
_RECENT_FAIL: Dict[int, datetime] = {}
_DEDUP: set[Tuple[str, int]] = set()
_LAST_BIO: Optional[str] = None
_LAST_PHOTO_ID: Optional[str] = None
_ME_ID: Optional[int] = None
_LISTENERS = []
_BIO_TASK: Optional[asyncio.Task] = None
_STARTUP_DONE = asyncio.Event()


def _now():
    return datetime.now(timezone.utc)


def _hash(v: Any) -> str:
    return hashlib.md5(repr(v).encode("utf-8", "replace")).hexdigest()[:12]


def _cache_put(key: Tuple[int, int], value: Dict[str, Any]):
    if key in _CACHE:
        _CACHE[key] = value
        return
    _CACHE[key] = value
    _CACHE_KEYS.append(key)
    while len(_CACHE_KEYS) > CACHE_MAX:
        oldest = _CACHE_KEYS.pop(0)
        _CACHE.pop(oldest, None)


def _cache_get(key: Tuple[int, int]) -> Optional[Dict[str, Any]]:
    return _CACHE.get(key)


def _dedup_mark(kind: str, mid: int) -> bool:
    k = (kind, mid)
    if k in _DEDUP:
        return False
    _DEDUP.add(k)
    if len(_DEDUP) > 5000:
        _DEDUP.clear()
    return True


async def _get_cfg() -> Dict[str, Any]:
    cfg = await _cfgdb.find_one({"_id": "singleton"}) or {}
    defaults = {
        "_id": "singleton",
        "main_id": None,
        "enabled": False,
        "protect_enabled": True,
        "wipe_on_boot": False,
        "bio_clone": True,
        "wipe_promo_protect": True,
        "wipe_recent_self_hours": RECENT_SELF_HOURS,
        "last_wipe_ts": None,
    }
    upd = {k: v for k, v in defaults.items() if k not in cfg}
    if upd:
        await _cfgdb.update_one({"_id": "singleton"}, {"$set": upd}, upsert=True)
        cfg.update(upd)
    return cfg


async def _set_cfg(**kwargs):
    await _cfgdb.update_one({"_id": "singleton"}, {"$set": kwargs}, upsert=True)


async def _save_chat(chat_id: int, role: str, title: str, added_by: int, perm_state: str = "unknown", active: bool = True):
    await _chatsdb.update_one(
        {"chat_id": chat_id},
        {"$set": {
            "role": role,
            "title": title,
            "added_by": added_by,
            "active": active,
            "perm_state": perm_state,
            "last_healthy_ts": _now() if perm_state == "ok" else None,
        }, "$setOnInsert": {"added_at": _now()}},
        upsert=True,
    )


async def _get_chat(chat_id: int):
    return await _chatsdb.find_one({"chat_id": chat_id})


async def _load_state():
    global _MAIN, _SUBS, _ENABLED, _PROTECT, _WIPE_PROMO_PROTECT, _WIPE_RECENT_HOURS, _WIPE_BOOT, _BIO_CLONE, _CLONE_ADMINS
    cfg = await _get_cfg()
    _ENABLED = bool(cfg.get("enabled", False))
    _PROTECT = bool(cfg.get("protect_enabled", True))
    _WIPE_PROMO_PROTECT = bool(cfg.get("wipe_promo_protect", True))
    _WIPE_RECENT_HOURS = int(cfg.get("wipe_recent_self_hours", RECENT_SELF_HOURS))
    _WIPE_BOOT = bool(cfg.get("wipe_on_boot", False))
    _BIO_CLONE = bool(cfg.get("bio_clone", True))
    _MAIN = cfg.get("main_id")
    _SUBS = set()
    main_doc = None
    if _MAIN:
        main_doc = await _chatsdb.find_one({"chat_id": _MAIN})
    async for doc in _chatsdb.find({"active": True}):
        if doc.get("role") == "sub":
            _SUBS.add(int(doc["chat_id"]))
    if not main_doc and _MAIN:
        try:
            c = await app.get_chat(_MAIN)
            await _save_chat(_MAIN, "main", c.title or str(_MAIN), 0, "unknown")
        except Exception:
            pass
    cur = _adminsdb.find({})
    _CLONE_ADMINS = {int(OWNER_ID)}
    for a in ADMINS:
        try:
            _CLONE_ADMINS.add(int(a))
        except Exception:
            pass
    async for d in cur:
        try:
            _CLONE_ADMINS.add(int(d["user_id"]))
        except Exception:
            pass


async def _is_clone_admin(uid: int) -> bool:
    try:
        return int(uid) in _CLONE_ADMINS or int(uid) == int(OWNER_ID)
    except Exception:
        return False


async def _verify_rights(chat_id: int, for_role: str) -> Tuple[bool, list[str]]:
    missing = []
    try:
        me = await app.get_chat_member(chat_id, "me")
    except errors.ChatAdminRequired:
        return False, ["not_admin"]
    except (errors.ChannelPrivate, errors.ChatInvalid, errors.ChannelIdInvalid):
        return False, ["no_access"]
    except Exception:
        return False, ["unknown"]
    rights = getattr(me, "privileges", None)
    if rights is None:
        if for_role == "sub":
            return False, ["not_admin"]
        return False, ["not_admin"]
    required = ["can_post_messages", "can_edit_messages", "can_delete_messages"]
    if for_role == "main":
        required += []
    for r in required:
        if not bool(getattr(rights, r, False)):
            missing.append(r)
    if for_role == "main" and _BIO_CLONE:
        if not bool(getattr(rights, "can_change_info", False)):
            missing.append("can_change_info")
    return (len(missing) == 0), missing


async def _set_chat_state(chat_id: int, perm_state: str):
    await _chatsdb.update_one(
        {"chat_id": chat_id},
        {"$set": {"perm_state": perm_state, "last_healthy_ts": _now() if perm_state == "ok" else None}},
    )


async def _warm_cache():
    _CACHE.clear()
    _CACHE_KEYS.clear()
    cur = _mapdb.find({"main_id": _MAIN}).sort("_id", -1).limit(CACHE_MAX) if _MAIN else []
    async for d in cur:
        try:
            key = (int(d["main_id"]), int(d["msg_id"]))
            _cache_put(key, {
                "subs": {int(k): int(v) for k, v in (d.get("subs") or {}).items()},
                "snap": d.get("last_snap") or {},
                "is_album": bool(d.get("is_album")),
                "album_key": d.get("album_key"),
            })
        except Exception:
            pass


async def _save_mapping(main_mid: int, subs_map: Dict[int, int], is_album: bool = False, album_key: Optional[str] = None, snap: Optional[Dict[str, str]] = None):
    if not _MAIN:
        return
    doc = {
        "main_id": _MAIN,
        "msg_id": main_mid,
        "subs": {str(k): v for k, v in subs_map.items()},
        "is_album": is_album,
        "album_key": album_key,
        "ts": _now(),
        "last_snap": snap or {},
    }
    await _mapdb.update_one(
        {"main_id": _MAIN, "msg_id": main_mid},
        {"$set": doc},
        upsert=True,
    )
    _cache_put((_MAIN, main_mid), {
        "subs": dict(subs_map),
        "snap": snap or {},
        "is_album": is_album,
        "album_key": album_key,
    })


async def _load_mapping(main_mid: int) -> Optional[Dict[str, Any]]:
    if not _MAIN:
        return None
    key = (_MAIN, main_mid)
    c = _cache_get(key)
    if c is not None:
        return c
    d = await _mapdb.find_one({"main_id": _MAIN, "msg_id": main_mid})
    if not d:
        return None
    c = {
        "subs": {int(k): int(v) for k, v in (d.get("subs") or {}).items()},
        "snap": d.get("last_snap") or {},
        "is_album": bool(d.get("is_album")),
        "album_key": d.get("album_key"),
    }
    _cache_put(key, c)
    return c


async def _unset_sub_mapping(main_mid: int, sub_id: int):
    if not _MAIN:
        return
    key = (_MAIN, main_mid)
    c = _cache_get(key)
    if c:
        c["subs"].pop(sub_id, None)
    await _mapdb.update_one(
        {"main_id": _MAIN, "msg_id": main_mid},
        {"$unset": {f"subs.{sub_id}": ""}},
    )


async def _update_snap(main_mid: int, snap: Dict[str, str]):
    if not _MAIN:
        return
    key = (_MAIN, main_mid)
    c = _cache_get(key)
    if c:
        c["snap"] = snap
    await _mapdb.update_one(
        {"main_id": _MAIN, "msg_id": main_mid},
        {"$set": {"last_snap": snap, "ts": _now()}},
        upsert=True,
    )


async def _build_whitelist(sub_id: int) -> set:
    ids: set[int] = set()
    try:
        cutoff = _now() - timedelta(days=30)
        async for d in _promodb.find({"post_type": "promo_track", "promo_channel_id": sub_id, "_id": {"$gte": None}}):
            ts = d.get("ts") or d.get("posted_at") or cutoff
            try:
                if ts < cutoff:
                    continue
            except Exception:
                pass
            mid = d.get("last_msg_id")
            if isinstance(mid, int):
                ids.add(mid)
    except Exception:
        return set()
    return ids


async def _wipe_sub(sub_id: int, force: bool = False, admin_msg: Any = None) -> Tuple[int, int, bool]:
    deleted = 0
    skipped = 0
    aborted = False
    whitelist: set[int] = set()
    recent_cutoff = _now() - timedelta(hours=_WIPE_RECENT_HOURS if not force else 0)
    if _WIPE_PROMO_PROTECT and not force:
        whitelist = await _build_whitelist(sub_id)
        if whitelist is None:
            return 0, 0, True
    try:
        await app.get_chat(sub_id)
    except Exception:
        return 0, 0, True
    chunk: list[int] = []
    chunk_msgs: list[Any] = []
    try:
        async for m in app.get_chat_history(sub_id):
            if not force and m.id in whitelist:
                skipped += 1
                continue
            if not force and (m.from_user and getattr(m.from_user, "is_self", False)) and m.date and m.date.replace(tzinfo=timezone.utc) > recent_cutoff:
                skipped += 1
                continue
            if m.service:
                continue
            chunk.append(m.id)
            chunk_msgs.append(m)
            if len(chunk) >= WIPE_CHUNK:
                try:
                    await app.delete_messages(sub_id, chunk)
                    deleted += len(chunk)
                except errors.FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                    try:
                        await app.delete_messages(sub_id, chunk)
                        deleted += len(chunk)
                    except Exception:
                        pass
                except Exception:
                    pass
                chunk = []
                chunk_msgs = []
                if admin_msg:
                    try:
                        await admin_msg.edit_text(f"<code>[clone]</code> wiping sub <code>{sub_id}</code>... deleted={deleted}, skipped={skipped}")
                    except Exception:
                        pass
                await asyncio.sleep(0.5)
        if chunk:
            try:
                await app.delete_messages(sub_id, chunk)
                deleted += len(chunk)
            except errors.FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                try:
                    await app.delete_messages(sub_id, chunk)
                    deleted += len(chunk)
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        aborted = True
    return deleted, skipped, aborted


async def _bulk_wipe(force: bool = False, admin_msg: Any = None):
    global _PROMO_WHITELIST
    _PROMO_WHITELIST = {}
    sem = asyncio.Semaphore(WIPE_CONCURRENCY)
    results: Dict[int, Tuple[int, int, bool]] = {}

    async def _run(sub_id: int):
        async with sem:
            results[sub_id] = await _wipe_sub(sub_id, force=force, admin_msg=admin_msg)

    tasks = [asyncio.create_task(_run(s)) for s in list(_SUBS)]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await _set_cfg(last_wipe_ts=_now())
    _PROMO_WHITELIST = {}
    return results


def _attachment_kwargs(m: Message, for_album_input: bool = False) -> Tuple[str, Any, Dict[str, Any]]:
    kwargs: Dict[str, Any] = {}
    media_type = "text"
    media_arg = None
    if m.text:
        return "text", None, kwargs
    caption = m.caption or m.text or None
    cap_ents = m.caption_entities or []
    if m.photo:
        media_type = "photo"
        media_arg = m.photo.file_id
        kwargs.update(caption=caption, caption_entities=cap_ents, has_spoiler=getattr(m, "has_media_spoiler", False))
    elif m.video:
        media_type = "video"
        media_arg = m.video.file_id
        kwargs.update(caption=caption, caption_entities=cap_ents, duration=m.video.duration, width=m.video.width, height=m.video.height, supports_streaming=m.video.supports_streaming, has_spoiler=getattr(m, "has_media_spoiler", False))
        t = getattr(m.video, "thumbs", None) or getattr(m.video, "thumbnail", None)
        if t:
            try:
                th = t[0] if isinstance(t, list) else t
                kwargs.update(thumb=th.file_id)
            except Exception:
                pass
    elif m.animation:
        media_type = "animation"
        media_arg = m.animation.file_id
        kwargs.update(caption=caption, caption_entities=cap_ents, duration=m.animation.duration, width=m.animation.width, height=m.animation.height)
    elif m.audio:
        media_type = "audio"
        media_arg = m.audio.file_id
        kwargs.update(caption=caption, caption_entities=cap_ents, duration=m.audio.duration, performer=m.audio.performer, title=m.audio.title)
    elif m.voice:
        media_type = "voice"
        media_arg = m.voice.file_id
        kwargs.update(caption=caption, caption_entities=cap_ents, duration=m.voice.duration)
    elif m.document:
        media_type = "document"
        media_arg = m.document.file_id
        kwargs.update(caption=caption, caption_entities=cap_ents, file_name=m.document.file_name)
        t = getattr(m.document, "thumbs", None) or getattr(m.document, "thumbnail", None)
        if t:
            try:
                th = t[0] if isinstance(t, list) else t
                kwargs.update(thumb=th.file_id)
            except Exception:
                pass
    elif m.video_note:
        media_type = "video_note"
        media_arg = m.video_note.file_id
        kwargs.update(duration=m.video_note.duration, length=m.video_note.length)
    elif m.sticker:
        media_type = "sticker"
        media_arg = m.sticker.file_id
        kwargs.update(emoji=m.sticker.emoji)
    elif m.contact:
        media_type = "contact"
        media_arg = m.contact
    elif m.location:
        media_type = "location"
        media_arg = m.location
    elif m.venue:
        media_type = "venue"
        media_arg = m.venue
    elif m.poll:
        media_type = "poll"
        media_arg = m.poll
    elif m.game:
        media_type = "game"
        media_arg = m.game
    else:
        media_type = "copy"
        media_arg = None
    return media_type, media_arg, kwargs


def _build_album_input(media_type: str, file_id: str, m: Message):
    cap = m.caption or ""
    cent = m.caption_entities or []
    if media_type == "photo":
        return InputMediaPhoto(media=file_id, caption=cap, caption_entities=cent, has_spoiler=getattr(m, "has_media_spoiler", False))
    if media_type == "video":
        return InputMediaVideo(media=file_id, caption=cap, caption_entities=cent, width=m.video.width, height=m.video.height, duration=m.video.duration, supports_streaming=m.video.supports_streaming, has_spoiler=getattr(m, "has_media_spoiler", False))
    if media_type == "animation":
        return InputMediaAnimation(media=file_id, caption=cap, caption_entities=cent, width=m.animation.width, height=m.animation.height, duration=m.animation.duration)
    if media_type == "audio":
        return InputMediaAudio(media=file_id, caption=cap, caption_entities=cent, duration=m.audio.duration, performer=m.audio.performer, title=m.audio.title)
    if media_type == "document":
        return InputMediaDocument(media=file_id, caption=cap, caption_entities=cent, file_name=m.document.file_name)
    return None


def _snap_of(m: Message) -> Dict[str, str]:
    return {
        "text_hash": _hash(m.text or ""),
        "caption_hash": _hash(m.caption or ""),
        "entities_hash": _hash(m.entities or []),
        "caption_entities_hash": _hash(m.caption_entities or []),
        "markup_hash": _hash(m.reply_markup.inline_keyboard if m.reply_markup else None),
        "media_hash": _hash(_media_key(m)),
    }


def _media_key(m: Message) -> Optional[str]:
    for attr in ("photo", "video", "animation", "audio", "voice", "document", "video_note", "sticker"):
        obj = getattr(m, attr, None)
        if obj is not None:
            return f"{attr}:{getattr(obj, 'file_id', '')}"
    return None


async def _resolve_reply_to(sub_id: int, m: Message) -> Optional[int]:
    if not (m.reply_to_message and _MAIN):
        return None
    rt = m.reply_to_message
    if getattr(rt, "chat", None) and rt.chat.id != _MAIN:
        return None
    rid = getattr(rt, "id", None) or getattr(rt, "message_id", None)
    if not rid:
        return None
    mp = await _load_mapping(rid)
    if not mp:
        return None
    return int(mp["subs"].get(sub_id)) if mp["subs"].get(sub_id) else None


async def _fanout_copy(m: Message) -> Optional[Dict[int, int]]:
    if not _ENABLED or not _MAIN:
        return None
    sem = asyncio.Semaphore(6)
    out: Dict[int, int] = {}

    async def _send(sub_id: int):
        if sub_id in _RECENT_FAIL:
            if _now() - _RECENT_FAIL[sub_id] < timedelta(minutes=5):
                return
        async with sem:
            try:
                reply_to = await _resolve_reply_to(sub_id, m)
                sent = await m.copy(
                    chat_id=sub_id,
                    reply_to_message_id=reply_to,
                    protect_content=_PROTECT,
                    reply_markup=m.reply_markup,
                )
                if sent is None:
                    return
                out[sub_id] = sent.id
                await _set_chat_state(sub_id, "ok")
                _RECENT_FAIL.pop(sub_id, None)
            except (errors.ChatAdminRequired, errors.ChannelPrivate, errors.ChatInvalid, errors.ChannelIdInvalid):
                _RECENT_FAIL[sub_id] = _now()
                await _set_chat_state(sub_id, "missing_admin")
            except errors.FloodWait as fw:
                await asyncio.sleep(fw.value + 1)
                try:
                    sent = await m.copy(
                        chat_id=sub_id,
                        reply_to_message_id=reply_to,
                        protect_content=_PROTECT,
                        reply_markup=m.reply_markup,
                    )
                    if sent:
                        out[sub_id] = sent.id
                        await _set_chat_state(sub_id, "ok")
                        _RECENT_FAIL.pop(sub_id, None)
                except Exception:
                    _RECENT_FAIL[sub_id] = _now()
            except Exception:
                _RECENT_FAIL[sub_id] = _now()

    tasks = [asyncio.create_task(_send(s)) for s in list(_SUBS)]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    return out or None


async def _fanout_edit(sub_id: int, sub_mid: int, m: Message, diff: set[str]):
    if "media_changed" in diff:
        mt, fid, kw = _attachment_kwargs(m)
        im = _build_album_input(mt, fid, m)
        if im is not None:
            for att in range(3):
                try:
                    await app.edit_message_media(chat_id=sub_id, message_id=sub_mid, media=im, reply_markup=m.reply_markup)
                    return
                except errors.FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                except errors.MessageNotModified:
                    return
                except Exception:
                    await asyncio.sleep(1.0 * (att + 1))
    try:
        if m.text and ("text_changed" in diff or "entities_changed" in diff or "markup_changed" in diff):
            await app.edit_message_text(
                chat_id=sub_id, message_id=sub_mid,
                text=m.text.html if getattr(m.text, "html", None) else m.text,
                entities=m.entities,
                parse_mode=None if m.entities else enums.ParseMode.DEFAULT,
                reply_markup=m.reply_markup,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )
            return
        if (m.caption or m.photo or m.video or m.document or m.audio or m.animation) and (
            "caption_changed" in diff or "caption_entities_changed" in diff or "markup_changed" in diff or "media_changed" in diff
        ):
            for att in range(3):
                try:
                    await app.edit_message_caption(
                        chat_id=sub_id, message_id=sub_mid,
                        caption=m.caption or "",
                        caption_entities=m.caption_entities,
                        parse_mode=None if m.caption_entities else enums.ParseMode.DEFAULT,
                        reply_markup=m.reply_markup,
                    )
                    return
                except errors.FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                except errors.MessageNotModified:
                    return
                except Exception:
                    await asyncio.sleep(0.8 * (att + 1))
            if "markup_changed" in diff:
                try:
                    await app.edit_message_reply_markup(chat_id=sub_id, message_id=sub_mid, reply_markup=m.reply_markup)
                except errors.MessageNotModified:
                    pass
            return
        if "markup_changed" in diff:
            for att in range(3):
                try:
                    await app.edit_message_reply_markup(chat_id=sub_id, message_id=sub_mid, reply_markup=m.reply_markup)
                    return
                except errors.FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                except errors.MessageNotModified:
                    return
                except Exception:
                    await asyncio.sleep(0.8 * (att + 1))
    except errors.MessageIdInvalid:
        await _unset_sub_mapping(m.id, sub_id)
    except errors.MessageNotModified:
        pass
    except errors.FloodWait as fw:
        await asyncio.sleep(fw.value + 1)
    except (errors.ChatAdminRequired, errors.ChannelPrivate, errors.ChannelIdInvalid):
        _RECENT_FAIL[sub_id] = _now()
        await _set_chat_state(sub_id, "missing_admin")


def _compute_diff(old_snap: Dict[str, str], new_snap: Dict[str, str]) -> set[str]:
    diff: set[str] = set()
    for a, b in (
        ("text_hash", "text_changed"),
        ("caption_hash", "caption_changed"),
        ("entities_hash", "entities_changed"),
        ("caption_entities_hash", "caption_entities_changed"),
        ("markup_hash", "markup_changed"),
        ("media_hash", "media_changed"),
    ):
        if old_snap.get(a) != new_snap.get(a):
            diff.add(b)
    return diff


async def _handle_edited_after_debounce(m: Message, mapping: Dict[str, Any]):
    new_snap = _snap_of(m)
    old_snap = mapping.get("snap") or {}
    diff = _compute_diff(old_snap, new_snap)
    if not diff:
        return
    sem = asyncio.Semaphore(6)

    async def _one(sub_id: int, sub_mid: int):
        async with sem:
            try:
                await _fanout_edit(int(sub_id), int(sub_mid), m, diff)
                await _set_chat_state(int(sub_id), "ok")
            except Exception:
                pass

    tasks = [asyncio.create_task(_one(sid, smid)) for sid, smid in list(mapping.get("subs", {}).items())]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    await _update_snap(m.id, new_snap)


async def _schedule_edit(m: Message):
    key = (_MAIN or 0, m.id)
    if key in _EDIT_TASKS:
        t, _ = _EDIT_TASKS[key]
        if not t.done():
            t.cancel()
    mapping = await _load_mapping(m.id)
    if not mapping:
        return

    async def _runner():
        await asyncio.sleep(EDIT_DEBOUNCE)
        try:
            fresh = await app.get_messages(_MAIN, m.id)
            if fresh:
                await _handle_edited_after_debounce(fresh, mapping)
        except Exception:
            pass
        finally:
            _EDIT_TASKS.pop(key, None)

    t = asyncio.create_task(_runner())
    _EDIT_TASKS[key] = (t, _now().timestamp())


async def _fanout_delete(mids: list[int]):
    if not _ENABLED or not _MAIN:
        return
    sem = asyncio.Semaphore(6)

    async def _one_sub(sub_id: int):
        if sub_id in _RECENT_FAIL and _now() - _RECENT_FAIL[sub_id] < timedelta(minutes=5):
            return
        ids = []
        for mid in mids:
            mp = await _load_mapping(mid)
            if not mp:
                continue
            smid = mp["subs"].get(sub_id)
            if smid:
                ids.append(int(smid))
        if not ids:
            return
        for i in range(0, len(ids), WIPE_CHUNK):
            chunk = ids[i:i + WIPE_CHUNK]
            async with sem:
                for att in range(3):
                    try:
                        await app.delete_messages(sub_id, chunk)
                        await _set_chat_state(sub_id, "ok")
                        _RECENT_FAIL.pop(sub_id, None)
                        break
                    except errors.FloodWait as fw:
                        await asyncio.sleep(fw.value + 1)
                    except Exception:
                        await asyncio.sleep(0.5 * (att + 1))
                        break

    tasks = [asyncio.create_task(_one_sub(s)) for s in list(_SUBS)]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    for mid in mids:
        await _mapdb.delete_one({"main_id": _MAIN, "msg_id": mid})
        _CACHE.pop((_MAIN, mid), None)


async def _fanout_album(sub_ids: list[int], messages: list[Message]):
    sem = asyncio.Semaphore(6)
    album_key = f"album:{_MAIN}:{messages[0].id}"
    per_sub: Dict[int, list[int]] = {s: [] for s in sub_ids}

    async def _send_sub(sub_id: int):
        if sub_id in _RECENT_FAIL and _now() - _RECENT_FAIL[sub_id] < timedelta(minutes=5):
            return
        media_group = []
        for i, m in enumerate(messages):
            mt, fid, _ = _attachment_kwargs(m, for_album_input=True)
            im = _build_album_input(mt, fid, m)
            if im is None:
                return
            if i == 0 and _PROTECT:
                try:
                    im.protect_content = True
                except Exception:
                    pass
            media_group.append(im)
        async with sem:
            reply_to = await _resolve_reply_to(sub_id, messages[0])
            for att in range(3):
                try:
                    sent_msgs = await app.send_media_group(
                        chat_id=sub_id,
                        media=media_group,
                        reply_to_message_id=reply_to,
                    )
                    if sent_msgs:
                        for orig, snt in zip(messages, sent_msgs):
                            per_sub[sub_id].append((orig.id, snt.id))
                    await _set_chat_state(sub_id, "ok")
                    _RECENT_FAIL.pop(sub_id, None)
                    return
                except errors.FloodWait as fw:
                    await asyncio.sleep(fw.value + 1)
                except (errors.ChatAdminRequired, errors.ChannelPrivate, errors.ChannelIdInvalid):
                    _RECENT_FAIL[sub_id] = _now()
                    await _set_chat_state(sub_id, "missing_admin")
                    return
                except Exception:
                    await asyncio.sleep(1.0 * (att + 1))

    tasks = [asyncio.create_task(_send_sub(s)) for s in sub_ids]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    submap_first: Dict[int, int] = {}
    for sub_id, pairs in per_sub.items():
        for orig_id, sent_id in pairs:
            await _save_mapping(int(orig_id), {int(sub_id): int(sent_id)}, is_album=True, album_key=album_key)
            if pairs and pairs[0][0] == orig_id:
                submap_first[sub_id] = sent_id
    return submap_first


async def _flush_album(album_key: str):
    rec = _ALBUM_BUF.pop(album_key, None)
    if not rec:
        return
    msgs = sorted(rec["msgs"], key=lambda x: x.id)
    if not msgs:
        return
    subs_ready = list(_SUBS)
    await _fanout_album(subs_ready, msgs)


async def _schedule_album_flush(album_key: str):
    rec = _ALBUM_BUF[album_key]
    if rec.get("task") and not rec["task"].done():
        rec["task"].cancel()

    async def _waiter():
        await asyncio.sleep(ALBUM_WINDOW)
        await _flush_album(album_key)

    rec["task"] = asyncio.create_task(_waiter())


async def _set_bio_photo(main_chat, force: bool = False):
    global _LAST_BIO, _LAST_PHOTO_ID
    desc = getattr(main_chat, "description", None) or ""
    photo = getattr(main_chat, "photo", None)
    photo_id = None
    if photo:
        photo_id = getattr(photo, "big_file_id", None) or getattr(photo, "file_id", None)
    if desc != _LAST_BIO or force:
        _LAST_BIO = desc
        for s in list(_SUBS):
            try:
                await app.set_chat_description(s, desc)
            except Exception:
                pass
    if photo_id and photo_id != _LAST_PHOTO_ID:
        _LAST_PHOTO_ID = photo_id
        try:
            pfile = await app.download_media(photo_id, in_memory=True)
            if pfile:
                pfile.name = "chat_photo.jpg"
                for s in list(_SUBS):
                    try:
                        await app.set_chat_photo(s, photo=pfile)
                    except Exception:
                        pass
        except Exception:
            pass


async def _bio_loop():
    global _LAST_BIO, _LAST_PHOTO_ID
    _LAST_BIO = None
    _LAST_PHOTO_ID = None
    while True:
        await _STARTUP_DONE.wait()
        await asyncio.sleep(BIO_POLL)
        if not (_ENABLED and _MAIN and _BIO_CLONE):
            continue
        try:
            c = await app.get_chat(_MAIN)
            full = await app.invoke(raw.functions.channels.GetFullChannel(channel=await app.resolve_peer(_MAIN)))
            desc = getattr(full.full_chat, "about", "") or ""
            photo = getattr(c, "photo", None)
            photo_id = getattr(photo, "big_file_id", None) if photo else None
            if desc != _LAST_BIO and _LAST_BIO is not None:
                _LAST_BIO = desc
                for s in list(_SUBS):
                    try:
                        await app.set_chat_description(s, desc)
                    except Exception:
                        pass
            else:
                _LAST_BIO = desc
            if photo_id and photo_id != _LAST_PHOTO_ID:
                _LAST_PHOTO_ID = photo_id
                try:
                    pfile = await app.download_media(photo.big_file_id, in_memory=True)
                    if pfile:
                        pfile.name = "chat_photo.jpg"
                        for s in list(_SUBS):
                            try:
                                await app.set_chat_photo(s, photo=pfile)
                            except Exception:
                                pass
                except Exception:
                    pass
        except asyncio.CancelledError:
            return
        except Exception:
            await asyncio.sleep(BIO_POLL)


def _clone_admin_filter(flt, client, message):
    if not message.from_user:
        return False
    uid = message.from_user.id
    if message.chat and message.chat.type == enums.ChatType.PRIVATE:
        return uid in _CLONE_ADMINS or uid == OWNER_ID
    if _MAIN and message.chat and message.chat.id == _MAIN:
        return uid in _CLONE_ADMINS or uid == OWNER_ID
    return False


def _bulk_active(uid: int) -> bool:
    s = _BULK_SESS.get(uid)
    if not s:
        return False
    if _now() > s["ends_at"]:
        return False
    return s.get("status") == "open"


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["setmain"]), group=HANDLER_GROUP)
async def _cmd_setmain(client, message):
    if len(message.command) >= 2:
        tgt = message.command[1]
    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        tgt = message.reply_to_message.forward_from_chat.id
    else:
        return await message.reply_text("Usage: /setmain <chat_id|link> or reply to forwarded msg from channel")
    try:
        c = await app.get_chat(tgt)
    except Exception as e:
        return await message.reply_text(f"Cannot resolve chat: {e}")
    if c.type not in (enums.ChatType.CHANNEL,):
        return await message.reply_text("Target must be a channel.")
    ok, miss = await _verify_rights(c.id, "main")
    if not ok:
        return await message.reply_text(f"Missing rights on MAIN: {', '.join(miss)}")
    global _MAIN
    prev = _MAIN
    _MAIN = int(c.id)
    if prev and prev != _MAIN:
        prev_doc = await _get_chat(prev)
        if prev_doc and prev_doc.get("role") == "main":
            await _chatsdb.update_one({"chat_id": prev}, {"$set": {"role": "sub", "active": True}})
            _SUBS.add(int(prev))
    await _save_chat(c.id, "main", c.title or str(c.id), message.from_user.id, "ok", active=True)
    await _set_cfg(main_id=_MAIN)
    await message.reply_text(f"MAIN set to <b>{html.escape(c.title or str(c.id))}</b> (<code>{c.id}</code>).")


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["addclone", "addc"]), group=HANDLER_GROUP)
async def _cmd_addclone(client, message):
    if len(message.command) >= 2 and message.command[1] == "-b":
        if _bulk_active(message.from_user.id):
            return await message.reply_text("A bulk session is already open for you. Wait for it to finish or use /clonewipe.")
        try:
            import DURGESH.modules.zauto_promo as _zp
            ba = getattr(_zp, "bulk_add_active", {})
            br = getattr(_zp, "bulk_remove_active", {})
            if ba.get(message.chat.id) or br.get(message.chat.id):
                return await message.reply_text("⚠ Promo bulk add/remove is active in this chat. End it first or use a different chat.")
        except Exception:
            pass
        _BULK_SESS[message.from_user.id] = {
            "admin_id": message.from_user.id,
            "chat_id": message.chat.id,
            "trigger_msg_id": message.id,
            "started_at": _now(),
            "ends_at": _now() + timedelta(seconds=BULK_WINDOW),
            "collected": {},
            "status": "open",
        }
        await message.reply_text(f"⏱ Bulk mode ON for {BULK_WINDOW}s. Forward messages from target channels here; I'll silently collect.")
        asyncio.create_task(_bulk_finalize(message.from_user.id, message))
        return

    if len(message.command) >= 2:
        tgt = message.command[1]
    elif message.reply_to_message and message.reply_to_message.forward_from_chat:
        tgt = message.reply_to_message.forward_from_chat.id
    else:
        return await message.reply_text("Usage: /addclone <chat_id|link> or /addclone -b (bulk)")
    try:
        c = await app.get_chat(tgt)
    except Exception as e:
        return await message.reply_text(f"Cannot resolve chat: {e}")
    if c.type not in (enums.ChatType.CHANNEL,):
        return await message.reply_text("Target must be a channel.")
    ok, miss = await _verify_rights(c.id, "sub")
    state = "ok" if ok else "missing_admin"
    if _MAIN == int(c.id):
        return await message.reply_text("That is the MAIN channel.")
    await _save_chat(c.id, "sub", c.title or str(c.id), message.from_user.id, state, active=ok)
    if ok:
        _SUBS.add(int(c.id))
    return await message.reply_text(
        f"Added sub <b>{html.escape(c.title or str(c.id))}</b> (<code>{c.id}</code>). {'🟢 OK' if ok else '🔴 Missing rights: ' + ', '.join(miss)}"
    )


async def _bulk_finalize(uid: int, trigger_msg: Message):
    await asyncio.sleep(BULK_WINDOW)
    s = _BULK_SESS.get(uid)
    if not s or s.get("status") != "open":
        _BULK_SESS.pop(uid, None)
        return
    s["status"] = "validating"
    collected = dict(s["collected"])
    if not collected:
        _BULK_SESS.pop(uid, None)
        try:
            await trigger_msg.reply_text("Bulk session closed: no channels collected.")
        except Exception:
            pass
        return
    try:
        prog = await trigger_msg.reply_text(f"🔍 Checking {len(collected)} channels...")
    except Exception:
        prog = None
    sem = asyncio.Semaphore(VAL_CONCURRENCY)
    added = 0
    failed: list[Tuple[int, str]] = []
    skipped = 0

    async def _proc(chat_id: int, fwd_msg_id: int):
        nonlocal added, skipped
        if _MAIN == int(chat_id):
            skipped += 1
            return
        async with sem:
            ok, miss = await _verify_rights(chat_id, "sub")
            try:
                c = await app.get_chat(chat_id)
                title = c.title or str(chat_id)
            except Exception:
                title = str(chat_id)
            if ok:
                await _save_chat(chat_id, "sub", title, uid, "ok", active=True)
                _SUBS.add(int(chat_id))
                added += 1
                try:
                    await app.delete_messages(s["chat_id"], fwd_msg_id)
                except Exception:
                    pass
            else:
                failed.append((int(chat_id), ", ".join(miss)))

    tasks = [asyncio.create_task(_proc(cid, mid)) for cid, mid in collected.items()]
    await asyncio.gather(*tasks, return_exceptions=True)
    fail_lines = "\n".join(f"• <code>{cid}</code>: {r}" for cid, r in failed[:20])
    extra = f"\n... +{len(failed) - 20} more" if len(failed) > 20 else ""
    summary = (
        f"✅ Added: <b>{added}</b>\n"
        f"⚠️ Failed: <b>{len(failed)}</b>\n"
        f"ℹ️ Skipped: <b>{skipped}</b>"
    )
    if fail_lines:
        summary += f"\n\nFailed (msgs kept in chat for manual check):\n{fail_lines}{extra}"
    _BULK_SESS.pop(uid, None)
    if prog:
        try:
            await prog.edit_text(summary)
        except Exception:
            pass
    else:
        try:
            await trigger_msg.reply_text(summary)
        except Exception:
            pass


@app.on_message(filters.private & filters.forwarded, group=HANDLER_GROUP)
async def _bulk_listener(client, message):
    if not message.from_user:
        return
    uid = message.from_user.id
    if not _bulk_active(uid):
        return
    s = _BULK_SESS[uid]
    if message.chat.id != s["chat_id"]:
        return
    fc = message.forward_from_chat
    if not fc:
        return
    if fc.type != enums.ChatType.CHANNEL:
        return
    cid = int(fc.id)
    s["collected"][cid] = message.id


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["rmclone", "rmc"]), group=HANDLER_GROUP)
async def _cmd_rmclone(client, message):
    if len(message.command) < 2:
        return await message.reply_text("Usage: /rmclone <chat_id>")
    try:
        cid = int(message.command[1])
    except Exception:
        return await message.reply_text("Invalid chat id.")
    await _chatsdb.update_one({"chat_id": cid}, {"$set": {"active": False}})
    _SUBS.discard(cid)
    await message.reply_text(f"Removed sub <code>{cid}</code>.")


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["listclone", "lsc"]), group=HANDLER_GROUP)
async def _cmd_listclone(client, message):
    main_title = "unset"
    if _MAIN:
        try:
            c = await app.get_chat(_MAIN)
            main_title = f"{html.escape(c.title or str(_MAIN))} (<code>{_MAIN}</code>)"
        except Exception:
            main_title = f"<code>{_MAIN}</code>"
    lines = [f"MAIN: {main_title}", f"Protect: {'🔒 ON' if _PROTECT else '🔓 OFF'}", f"Service: {'🟢 ON' if _ENABLED else '🔴 OFF'}", f"Subs ({len(_SUBS)}):"]
    for s in list(_SUBS):
        doc = await _get_chat(s)
        state = (doc or {}).get("perm_state", "unknown")
        try:
            t = (doc or {}).get("title") or str(s)
        except Exception:
            t = str(s)
        icon = {"ok": "🟢", "missing_admin": "🔴"}.get(state, "🟡")
        lines.append(f" {icon} <code>{s}</code> - {html.escape(str(t))}")
    text = "\n".join(lines)
    if len(text) > 3900:
        text = text[:3800] + "\n... (truncated)"
    await message.reply_text(text)


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["clonestart"]), group=HANDLER_GROUP)
async def _cmd_start(client, message):
    global _ENABLED
    if not _MAIN:
        return await message.reply_text("Set MAIN first with /setmain.")
    if not _SUBS:
        return await message.reply_text("No subs added.")
    _ENABLED = False
    await _set_cfg(enabled=False)
    prog = await message.reply_text("🧹 Wiping sub channel histories (promo-safe)...")
    res = await _bulk_wipe(force=False, admin_msg=prog)
    ok_subs = sum(1 for _, _, ab in res.items() if not ab)
    bad_subs = sum(1 for _, _, ab in res.items() if ab)
    await _warm_cache()
    _ENABLED = True
    await _set_cfg(enabled=True)
    await prog.edit_text(f"Clone service ONLINE. MAIN=<code>{_MAIN}</code>, subs ok={ok_subs}, aborted={bad_subs}.")


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["clonestop"]), group=HANDLER_GROUP)
async def _cmd_stop(client, message):
    global _ENABLED
    _ENABLED = False
    await _set_cfg(enabled=False)
    await message.reply_text("Clone service STOPPED.")


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["clonewipe"]), group=HANDLER_GROUP)
async def _cmd_wipe(client, message):
    force = False
    args = message.text.split() if message.text else []
    if "--force" in args:
        force = True
    if not _SUBS:
        return await message.reply_text("No subs.")
    prog = await message.reply_text(f"🧹 Wiping subs... (force={force})")
    res = await _bulk_wipe(force=force, admin_msg=prog)
    total_d = sum(d for d, _, _ in res.values())
    total_s = sum(s for _, s, _ in res.values())
    bad = sum(1 for _, _, ab in res.values() if ab)
    await prog.edit_text(f"Wipe done. deleted={total_d}, skipped(promo/recent)={total_s}, aborted={bad}.")


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["cloneprotect"]), group=HANDLER_GROUP)
async def _cmd_protect(client, message):
    global _PROTECT
    args = message.command
    if len(args) >= 2:
        v = args[1].lower()
        if v in ("on", "1", "true"):
            _PROTECT = True
        elif v in ("off", "0", "false"):
            _PROTECT = False
        else:
            return await message.reply_text("Usage: /cloneprotect [on|off]")
    else:
        _PROTECT = not _PROTECT
    await _set_cfg(protect_enabled=_PROTECT)
    await message.reply_text(f"Protect {'🔒 ON' if _PROTECT else '🔓 OFF'}.")


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["cloneadmins"]), group=HANDLER_GROUP)
async def _cmd_clone_admins(client, message):
    args = message.command
    if len(args) < 3:
        lst = "\n".join(f"• <code>{u}</code>" for u in sorted(_CLONE_ADMINS))
        return await message.reply_text(f"Usage: /cloneadmins add|rm <user_id>\nCurrent:\n{lst}")
    act, uid_s = args[1], args[2]
    try:
        uid = int(uid_s)
    except Exception:
        return await message.reply_text("Invalid user id.")
    if act == "add":
        _CLONE_ADMINS.add(uid)
        await _adminsdb.update_one({"user_id": uid}, {"$set": {"user_id": uid}}, upsert=True)
        return await message.reply_text(f"Added clone admin <code>{uid}</code>.")
    if act == "rm":
        _CLONE_ADMINS.discard(uid)
        await _adminsdb.delete_many({"user_id": uid})
        return await message.reply_text(f"Removed clone admin <code>{uid}</code>.")
    await message.reply_text("Use add or rm.")


@app.on_message(filters.create(_clone_admin_filter) & filters.command(["clonestatus"]), group=HANDLER_GROUP)
async def _cmd_status(client, message):
    promo_state = "unknown"
    try:
        pcfg = await _promodb.find_one({"_id": "config"}) or {}
        promo_state = "🟢 ON" if pcfg.get("promo_enabled", True) else "🔴 OFF"
    except Exception:
        pass
    healthy = 0
    for s in list(_SUBS):
        doc = await _get_chat(s)
        if (doc or {}).get("perm_state") == "ok":
            healthy += 1
    lines = [
        f"MAIN: <code>{_MAIN or 'unset'}</code>",
        f"Service: {'🟢 ON' if _ENABLED else '🔴 OFF'}",
        f"Protect: {'🔒 ON' if _PROTECT else '🔓 OFF'}",
        f"SUBS total: <b>{len(_SUBS)}</b>, healthy: <b>{healthy}</b>",
        f"Promo system: {promo_state}",
    ]
    await message.reply_text("\n".join(lines))


@app.on_message(
    filters.channel & ~filters.service,
    group=HANDLER_GROUP,
)
async def _on_new_post(client, message):
    if not (_ENABLED and _MAIN):
        return
    if message.chat.id != _MAIN:
        return
    if message.outgoing:
        return
    if message.from_user and getattr(message.from_user, "is_self", False):
        return
    if not _dedup_mark("new", message.id):
        return
    mgid = message.media_group_id
    if mgid:
        album_key = f"mg:{_MAIN}:{mgid}"
        if album_key not in _ALBUM_BUF:
            _ALBUM_BUF[album_key] = {"msgs": [], "task": None, "mgid": mgid}
            if len(_ALBUM_BUF) > ALBUM_MAP_MAX:
                oldest_key = next(iter(_ALBUM_BUF))
                rec = _ALBUM_BUF.pop(oldest_key)
                if rec.get("task") and not rec["task"].done():
                    rec["task"].cancel()
        _ALBUM_BUF[album_key]["msgs"].append(message)
        await _schedule_album_flush(album_key)
        return
    sent_map = await _fanout_copy(message)
    if sent_map:
        await _save_mapping(message.id, sent_map, snap=_snap_of(message))


@app.on_edited_message(
    filters.channel & ~filters.service,
    group=HANDLER_GROUP,
)
async def _on_edit(client, message):
    if not (_ENABLED and _MAIN):
        return
    if message.chat.id != _MAIN:
        return
    if message.outgoing:
        return
    await _schedule_edit(message)


@app.on_deleted_messages(group=HANDLER_GROUP)
async def _on_delete(client, messages):
    if not (_ENABLED and _MAIN):
        return
    ids = []
    for m in messages:
        cid = None
        try:
            cid = m.chat.id
        except Exception:
            cid = None
        if cid and cid != _MAIN:
            continue
        ids.append(m.id)
    if ids:
        await _fanout_delete(ids)


@app.on_raw_update(group=HANDLER_GROUP)
async def _on_raw(client, update, users, chats):
    if not (_ENABLED and _MAIN):
        return
    if isinstance(update, raw.types.UpdatePinnedChannelMessages):
        try:
            peer = update.channel_id
            if peer and getattr(peer, "channel_id", None):
                local_id = int("-100" + str(peer.channel_id))
            else:
                local_id = int(f"-100{peer}") if str(peer).lstrip("-").isdigit() else None
            if local_id != _MAIN:
                return
            for mid in (update.messages or []):
                mp = await _load_mapping(int(mid))
                if not mp:
                    continue
                for sid, smid in mp["subs"].items():
                    try:
                        await app.pin_chat_message(sid, smid, both_sides=False)
                    except Exception:
                        pass
        except Exception:
            return
    elif isinstance(update, raw.types.UpdateChatPhoto):
        try:
            pass
        except Exception:
            pass


async def _revalidate():
    sem = asyncio.Semaphore(VAL_CONCURRENCY)
    all_chats = []
    if _MAIN:
        all_chats.append((_MAIN, "main"))
    for s in list(_SUBS):
        all_chats.append((s, "sub"))

    async def _check(cid, role):
        async with sem:
            ok, miss = await _verify_rights(cid, role)
            await _set_chat_state(cid, "ok" if ok else "missing_admin")

    tasks = [asyncio.create_task(_check(c, r)) for c, r in all_chats]
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _startup():
    global _ME_ID, _BIO_TASK
    await app.get_me()
    _ME_ID = app.me.id
    await _load_state()
    await _ensure_indexes()
    await _revalidate()
    await _warm_cache()
    if _ENABLED and _MAIN and _SUBS and _WIPE_BOOT:
        await _bulk_wipe(force=False)
    _STARTUP_DONE.set()
    if _BIO_TASK is None or _BIO_TASK.done():
        _BIO_TASK = asyncio.create_task(_bio_loop())


async def _ensure_indexes():
    try:
        await _mapdb.create_index([("main_id", 1), ("msg_id", 1)], unique=True)
        await _mapdb.create_index([("ts", 1)], expireAfterSeconds=TTL_DAYS * 24 * 3600)
        await _chatsdb.create_index([("chat_id", 1)], unique=True)
        await _chatsdb.create_index([("role", 1), ("active", 1)])
        await _adminsdb.create_index([("user_id", 1)], unique=True)
        await _cfgdb.update_one({"_id": "singleton"}, {"$setOnInsert": {
            "main_id": None, "enabled": False, "protect_enabled": True, "wipe_on_boot": False,
            "bio_clone": True, "wipe_promo_protect": True, "wipe_recent_self_hours": RECENT_SELF_HOURS,
        }}, upsert=True)
    except Exception:
        pass


@app.on_message(filters.service, group=-1)
async def _svc_boot_trigger(client, message):
    pass


asyncio.create_task(_startup())
