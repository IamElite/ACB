import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode
from DURGESH import app
from DURGESH.database import db

apauthdb = db.apauth_channels

# -------------------- BACKGROUND TASKS STORAGE -------------------- #
running_tasks = {}  # {main_channel_id: task}

# -------------------- TIME PARSER -------------------- #

def parse_promo_time(time_str: str) -> int:
    """Convert time string like 5h, 5d, 5m to seconds"""
    if not time_str:
        return 5 * 3600  # default 5 hours
    
    time_str = time_str.strip().lower()
    match = re.match(r'^(\d+)([hdm])$', time_str)
    
    if not match:
        return 5 * 3600
    
    value = int(match.group(1))
    unit = match.group(2)
    
    conversions = {
        'h': 3600,         # hours
        'd': 86400,        # days
        'm': 2592000       # months (30 days)
    }
    
    return value * conversions.get(unit, 3600)

def format_time(seconds: int) -> str:
    """Format seconds to readable time"""
    if seconds >= 2592000:
        return f"{seconds // 2592000}m"
    elif seconds >= 86400:
        return f"{seconds // 86400}d"
    else:
        return f"{seconds // 3600}h"

# -------------------- DB HELPERS -------------------- #

async def add_main_channel(chat_id: int):
    """Add main channel (source) from where to promote"""
    await apauthdb.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {
            "chat_id": str(chat_id),
            "is_main": True,
            "promo_channels": [],
            "forward_tag": True,  # on = with tag
            "promo_interval": "5h",
            "promo_interval_seconds": 18000,
            "last_promo_time": None,
            "posted_messages": [],  # Store message IDs for cycling
            "active_promo_posts": {},  # {promo_channel_id: [msg_ids]}
            "is_active": True
        }},
        upsert=True
    )

async def add_promo_channels(main_id: int, promo_ids: List[int]):
    """Add multiple promo channels to main channel"""
    data = await apauthdb.find_one({"chat_id": str(main_id)})
    if not data:
        return False
    
    existing = data.get("promo_channels", [])
    updated = list(set(existing + [str(pid) for pid in promo_ids]))
    
    await apauthdb.update_one(
        {"chat_id": str(main_id)},
        {"$set": {"promo_channels": updated}}
    )
    return True

async def remove_promo_channel(main_id: int, promo_id: int):
    """Remove a promo channel"""
    data = await apauthdb.find_one({"chat_id": str(main_id)})
    if not data:
        return False
    
    promo_list = data.get("promo_channels", [])
    if str(promo_id) in promo_list:
        promo_list.remove(str(promo_id))
        await apauthdb.update_one(
            {"chat_id": str(main_id)},
            {"$set": {"promo_channels": promo_list}}
        )
        return True
    return False

async def update_promo_settings(chat_id: int, forward_tag: bool, interval: str):
    """Update promo settings"""
    await apauthdb.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {
            "forward_tag": forward_tag,
            "promo_interval": interval,
            "promo_interval_seconds": parse_promo_time(interval)
        }}
    )
    
    # Restart task with new interval
    await restart_promo_task(chat_id)

async def get_main_channel_data(chat_id: int) -> Dict:
    """Get main channel data"""
    data = await apauthdb.find_one({"chat_id": str(chat_id)})
    return data

async def store_posted_message(main_id: int, msg_id: int):
    """Store message ID for later cycling"""
    await apauthdb.update_one(
        {"chat_id": str(main_id)},
        {"$addToSet": {"posted_messages": msg_id}}
    )

async def is_main_channel(chat_id: int) -> bool:
    """Check if channel is main"""
    data = await apauthdb.find_one({"chat_id": str(chat_id)})
    return bool(data and data.get("is_main"))

async def should_run_promo(chat_id: int) -> bool:
    """Check if enough time passed since last promo"""
    data = await get_main_channel_data(chat_id)
    
    if not data or not data.get("is_active"):
        return False
    
    last_promo = data.get("last_promo_time")
    interval = data.get("promo_interval_seconds", 18000)
    
    if not last_promo:
        return True
    
    last_time = datetime.fromisoformat(last_promo)
    elapsed = (datetime.now() - last_time).total_seconds()
    
    return elapsed >= interval

async def update_last_promo_time(chat_id: int):
    """Update last promotion time"""
    await apauthdb.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {"last_promo_time": datetime.now().isoformat()}}
    )

# -------------------- PROMO LOGIC -------------------- #

async def delete_old_posts(main_id: int, promo_channels: List[str]):
    """Delete old posts from promo channels"""
    data = await get_main_channel_data(main_id)
    if not data:
        return
    
    active_posts = data.get("active_promo_posts", {})
    
    for promo_id_str in promo_channels:
        promo_id = int(promo_id_str)
        old_msg_ids = active_posts.get(promo_id_str, [])
        
        if old_msg_ids:
            try:
                await app.delete_messages(promo_id, old_msg_ids)
                print(f"🗑️ Deleted {len(old_msg_ids)} old posts from {promo_id}")
            except Exception as e:
                print(f"❌ Failed to delete from {promo_id}: {e}")

async def send_new_posts(main_id: int, promo_channels: List[str], forward_tag: bool):
    """Send new posts to promo channels"""
    data = await get_main_channel_data(main_id)
    if not data:
        return
    
    posted_messages = data.get("posted_messages", [])
    
    if not posted_messages:
        print(f"⚠️ No messages to promote from {main_id}")
        return
    
    # Get the first message to cycle
    msg_id = posted_messages[0]
    
    # Rotate list (move first to last for cycling)
    posted_messages.append(posted_messages.pop(0))
    await apauthdb.update_one(
        {"chat_id": str(main_id)},
        {"$set": {"posted_messages": posted_messages}}
    )
    
    try:
        # Get the message from main channel
        main_msg = await app.get_messages(main_id, msg_id)
        
        if not main_msg:
            print(f"❌ Message {msg_id} not found in {main_id}")
            return
        
        # Send to all promo channels
        new_promo_posts = {}
        
        for promo_id_str in promo_channels:
            promo_id = int(promo_id_str)
            
            try:
                if forward_tag:
                    # Forward with tag
                    sent = await main_msg.forward(promo_id)
                else:
                    # Copy without tag (buttons preserved)
                    sent = await main_msg.copy(promo_id)
                
                # Store new message ID
                new_promo_posts[promo_id_str] = [sent.id]
                print(f"✅ Sent to {promo_id}")
                
                await asyncio.sleep(1)  # Avoid flood
                
            except Exception as e:
                print(f"❌ Failed to send to {promo_id}: {e}")
        
        # Update active promo posts
        await apauthdb.update_one(
            {"chat_id": str(main_id)},
            {"$set": {"active_promo_posts": new_promo_posts}}
        )
        
    except Exception as e:
        print(f"❌ Error in send_new_posts: {e}")

async def promo_loop(main_id: int):
    """Background task for auto promo"""
    print(f"🚀 Started promo loop for {main_id}")
    
    while True:
        try:
            data = await get_main_channel_data(main_id)
            
            if not data or not data.get("is_active"):
                print(f"⏸️ Promo loop stopped for {main_id}")
                break
            
            interval = data.get("promo_interval_seconds", 18000)
            promo_channels = data.get("promo_channels", [])
            forward_tag = data.get("forward_tag", True)
            
            if not promo_channels:
                print(f"⚠️ No promo channels for {main_id}, waiting...")
                await asyncio.sleep(60)  # Check again after 1 minute
                continue
            
            # Check if should run
            if await should_run_promo(main_id):
                print(f"🔄 Running promo for {main_id}")
                
                # Delete old posts
                await delete_old_posts(main_id, promo_channels)
                
                # Send new posts
                await send_new_posts(main_id, promo_channels, forward_tag)
                
                # Update last promo time
                await update_last_promo_time(main_id)
            
            # Sleep for interval
            await asyncio.sleep(interval)
            
        except asyncio.CancelledError:
            print(f"❌ Promo loop cancelled for {main_id}")
            break
        except Exception as e:
            print(f"❌ Error in promo_loop: {e}")
            await asyncio.sleep(60)  # Wait before retry

async def start_promo_task(main_id: int):
    """Start background promo task"""
    if main_id in running_tasks:
        print(f"ℹ️ Task already running for {main_id}")
        return
    
    task = asyncio.create_task(promo_loop(main_id))
    running_tasks[main_id] = task
    print(f"✅ Started promo task for {main_id}")

async def stop_promo_task(main_id: int):
    """Stop background promo task"""
    if main_id in running_tasks:
        running_tasks[main_id].cancel()
        del running_tasks[main_id]
        print(f"🛑 Stopped promo task for {main_id}")

async def restart_promo_task(main_id: int):
    """Restart promo task with new settings"""
    await stop_promo_task(main_id)
    await start_promo_task(main_id)

# -------------------- COMMANDS -------------------- #

@app.on_message(filters.command(["apauth"]))
async def add_main_promo_channel(client, message: Message):
    """Add main channel for auto promotion"""
    chat_id = None
    
    if message.reply_to_message and message.reply_to_message.forward_from_chat:
        chat_id = message.reply_to_message.forward_from_chat.id
    elif len(message.command) >= 2:
        try:
            if message.command[1].startswith("@"):
                chat = await client.get_chat(message.command[1])
                chat_id = chat.id
            elif message.command[1].lstrip('-').isdigit():
                chat_id = int(message.command[1])
        except Exception as e:
            return await message.reply_text(f"❌ Invalid channel!\nError: {e}")
    
    if not chat_id:
        return await message.reply_text(
            "❌ **Usage:**\n"
            "`/apauth <channel_id>`\n\n"
            "**OR** reply to a channel forwarded message"
        )
    
    try:
        await client.get_chat_member(chat_id, "me")
        chat = await client.get_chat(chat_id)
    except Exception as e:
        return await message.reply_text(f"⚠️ Error: {e}")
    
    await add_main_channel(chat_id)
    await start_promo_task(chat_id)
    
    await message.reply_text(
        f"✅ **Main Channel Authorized!**\n\n"
        f"📌 **Name:** {chat.title}\n"
        f"🆔 **ID:** `{chat_id}`\n"
        f"🔄 **Forward Tag:** ✅ ON\n"
        f"⏱️ **Interval:** 5h\n\n"
        f"💡 Background task started!\n"
        f"💡 Use `/apc` or `/apc -b` to add promo channels",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command(["addpromochnl", "apc"]))
async def add_promo_channels_cmd(client, message: Message):
    """
    Add promo channels
    /apc -b <main_id> : Bulk add (reply to first forwarded channel)
    /apc <main_id> : Single add (reply to forwarded channel OR provide channel_id)
    """
    
    args = message.text.split()
    is_bulk = "-b" in args
    
    # Get main channel ID
    main_id = None
    
    if is_bulk and len(args) >= 3:
        try:
            if args[2].startswith("@"):
                chat = await client.get_chat(args[2])
                main_id = chat.id
            elif args[2].lstrip('-').isdigit():
                main_id = int(args[2])
        except:
            pass
    elif not is_bulk and len(args) >= 2:
        try:
            if args[1].startswith("@"):
                chat = await client.get_chat(args[1])
                main_id = chat.id
            elif args[1].lstrip('-').isdigit():
                main_id = int(args[1])
        except:
            pass
    
    if not main_id:
        return await message.reply_text(
            "❌ **Usage:**\n\n"
            "**Bulk Add:**\n"
            "`/apc -b <main_id>` (reply to first forwarded channel)\n\n"
            "**Single Add:**\n"
            "`/apc <main_id>` (reply to forwarded channel)\n"
            "OR\n"
            "`/apc <main_id> <promo_channel_id>`"
        )
    
    if not await is_main_channel(main_id):
        return await message.reply_text("❌ Main channel not found! Use `/apauth` first.")
    
    promo_ids = []
    
    if is_bulk:
        # Bulk mode: collect from reply and next messages
        if not message.reply_to_message:
            return await message.reply_text("❌ Reply to first forwarded channel message!")
        
        if message.reply_to_message.forward_from_chat:
            promo_ids.append(message.reply_to_message.forward_from_chat.id)
        
        try:
            msg_id = message.reply_to_message.id
            for i in range(1, 50):
                try:
                    next_msg = await client.get_messages(message.chat.id, msg_id + i)
                    if next_msg.forward_from_chat:
                        promo_ids.append(next_msg.forward_from_chat.id)
                    else:
                        break
                except:
                    break
        except:
            pass
    else:
        # Single mode
        if message.reply_to_message and message.reply_to_message.forward_from_chat:
            promo_ids.append(message.reply_to_message.forward_from_chat.id)
        elif len(args) >= 3:
            try:
                if args[2].startswith("@"):
                    chat = await client.get_chat(args[2])
                    promo_ids.append(chat.id)
                elif args[2].lstrip('-').isdigit():
                    promo_ids.append(int(args[2]))
            except:
                pass
    
    if not promo_ids:
        return await message.reply_text("❌ No channels found to add!")
    
    success = await add_promo_channels(main_id, promo_ids)
    
    if success:
        mode_text = "Bulk" if is_bulk else "Single"
        await message.reply_text(
            f"✅ **Added {len(promo_ids)} promo channel{'s' if len(promo_ids) > 1 else ''}!**\n\n"
            f"📌 Main: `{main_id}`\n"
            f"🎯 Mode: {mode_text}\n"
            f"📢 Channels: {len(promo_ids)}\n\n"
            f"💡 Posts will cycle every 5h",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await message.reply_text("❌ Failed to add channels!")

@app.on_message(filters.command(["rmpc"]))
async def remove_promo_channel_cmd(client, message: Message):
    """Remove promo channel"""
    
    main_id = None
    promo_id = None
    
    if message.reply_to_message and message.reply_to_message.forward_from_chat:
        promo_id = message.reply_to_message.forward_from_chat.id
        
        if len(message.command) >= 2:
            try:
                if message.command[1].startswith("@"):
                    chat = await client.get_chat(message.command[1])
                    main_id = chat.id
                else:
                    main_id = int(message.command[1])
            except:
                pass
    elif len(message.command) >= 3:
        try:
            main_id = int(message.command[1])
            promo_id = int(message.command[2])
        except:
            pass
    
    if not main_id or not promo_id:
        return await message.reply_text(
            "❌ **Usage:**\n"
            "`/rmpc <main_id> <promo_id>`\n\n"
            "**OR** `/rmpc <main_id>` + reply to promo channel message"
        )
    
    success = await remove_promo_channel(main_id, promo_id)
    
    if success:
        await message.reply_text(
            f"✅ **Removed promo channel!**\n\n"
            f"🗑️ Removed: `{promo_id}`\n"
            f"📌 From: `{main_id}`",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await message.reply_text("❌ Channel not found in promo list!")

@app.on_message(filters.command(["apset"]))
async def update_promo_settings_cmd(client, message: Message):
    """Update promo settings"""
    
    args = message.text.split()
    chat_id = None
    forward_tag = True
    interval = "5h"
    
    if message.reply_to_message and message.reply_to_message.forward_from_chat:
        chat_id = message.reply_to_message.forward_from_chat.id
    elif len(args) >= 2:
        try:
            if args[1].startswith("@"):
                chat = await client.get_chat(args[1])
                chat_id = chat.id
            elif args[1].lstrip('-').isdigit():
                chat_id = int(args[1])
        except:
            pass
    
    if not chat_id:
        return await message.reply_text(
            "❌ **Usage:**\n"
            "`/apset <channel_id> -f on/off -t 5h`\n\n"
            "**Flags:**\n"
            "`-f` : Forward tag (on=with tag, off=no tag) - default: on\n"
            "`-t` : Interval (5h/5d/5m) - default: 5h"
        )
    
    if not await is_main_channel(chat_id):
        return await message.reply_text("❌ Not a main channel! Use `/apauth` first.")
    
    if "-f" in args:
        idx = args.index("-f")
        if idx + 1 < len(args):
            forward_tag = args[idx + 1].lower() in ["on", "true", "1"]
    
    if "-t" in args:
        idx = args.index("-t")
        if idx + 1 < len(args):
            interval = args[idx + 1]
    
    await update_promo_settings(chat_id, forward_tag, interval)
    
    await message.reply_text(
        f"✅ **Settings Updated!**\n\n"
        f"📌 **Channel:** `{chat_id}`\n"
        f"🔄 **Forward Tag:** {'❌ OFF' if not forward_tag else '✅ ON'}\n"
        f"⏱️ **Interval:** {interval}\n\n"
        f"💡 Task restarted with new settings!",
        parse_mode=ParseMode.MARKDOWN
    )

@app.on_message(filters.command(["aplist"]))
async def list_promo_channels(client, message: Message):
    """List all main channels"""
    
    cursor = apauthdb.find({"is_main": True})
    channels = [doc async for doc in cursor]
    
    if not channels:
        return await message.reply_text("⚠️ No auto-promo channels configured yet!")
    
    text = "✅ **Auto Promo Channels:**\n\n"
    
    for i, doc in enumerate(channels, start=1):
        chat_id = int(doc["chat_id"])
        promo_ids = doc.get("promo_channels", [])
        fwd_tag = "OFF" if not doc.get("forward_tag", True) else "ON"
        interval = doc.get("promo_interval", "5h")
        posted_count = len(doc.get("posted_messages", []))
        status = "🟢 Active" if chat_id in running_tasks else "🔴 Stopped"
        
        try:
            chat = await client.get_chat(chat_id)
            name = chat.title or "Unknown"
        except:
            name = "Unknown"
        
        text += f"**{i}. {name}**\n"
        text += f"   ├ ID: `{chat_id}`\n"
        text += f"   ├ Status: {status}\n"
        text += f"   ├ Promo: {len(promo_ids)} channels\n"
        text += f"   ├ Posts: {posted_count} messages\n"
        text += f"   ├ Tag: {fwd_tag}\n"
        text += f"   └ Interval: {interval}\n\n"
    
    await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

# -------------------- MESSAGE HANDLER -------------------- #

@app.on_message(filters.channel & ~filters.service)
async def store_channel_messages(client, message: Message):
    """Store messages from main channel for cycling"""
    
    if not await is_main_channel(message.chat.id):
        return
    
    # Store message ID for later promotion
    await store_posted_message(message.chat.id, message.id)
    print(f"📝 Stored message {message.id} from {message.chat.id}")

# -------------------- STARTUP -------------------- #

async def load_existing_tasks():
    """Load and start tasks for existing main channels"""
    cursor = apauthdb.find({"is_main": True, "is_active": True})
    channels = [doc async for doc in cursor]
    
    for doc in channels:
        chat_id = int(doc["chat_id"])
        await start_promo_task(chat_id)
        print(f"✅ Loaded task for channel {chat_id}")

# Start loading tasks on bot start
asyncio.create_task(load_existing_tasks())
print("🚀 Auto Promo system started!")
