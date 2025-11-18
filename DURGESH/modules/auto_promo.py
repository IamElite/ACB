import re
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List
from pyrogram import filters
from pyrogram.types import Message
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
            "forward_tag": True,
            "promo_interval": "5h",
            "promo_interval_seconds": 18000,
            "last_promo_time": None,
            "posted_messages": [],
            "current_post_index": 0,
            "active_promo_posts": {},
            "is_active": True
        }},
        upsert=True
    )

async def remove_main_channel(chat_id: int):
    """Remove main channel authorization"""
    # Stop task first
    await stop_promo_task(chat_id)
    
    # Remove from database
    result = await apauthdb.delete_one({"chat_id": str(chat_id)})
    return result.deleted_count > 0

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

async def update_or_create_promo_settings(chat_id: int, forward_tag: bool = None, interval: str = None):
    """Update existing settings OR create new if doesn't exist"""
    data = await apauthdb.find_one({"chat_id": str(chat_id)})
    
    if data:
        # Update existing
        update_data = {}
        
        if forward_tag is not None:
            update_data["forward_tag"] = forward_tag
        
        if interval is not None:
            update_data["promo_interval"] = interval
            update_data["promo_interval_seconds"] = parse_promo_time(interval)
        
        if update_data:
            await apauthdb.update_one(
                {"chat_id": str(chat_id)},
                {"$set": update_data}
            )
        
        await restart_promo_task(chat_id)
        return True
    else:
        # Create new with default values
        default_tag = forward_tag if forward_tag is not None else True
        default_interval = interval if interval is not None else "5h"
        
        await apauthdb.insert_one({
            "chat_id": str(chat_id),
            "is_main": True,
            "promo_channels": [],
            "forward_tag": default_tag,
            "promo_interval": default_interval,
            "promo_interval_seconds": parse_promo_time(default_interval),
            "last_promo_time": None,
            "posted_messages": [],
            "current_post_index": 0,
            "active_promo_posts": {},
            "is_active": True
        })
        
        await start_promo_task(chat_id)
        return True

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
    """Send new posts to promo channels (cycling through all posts)"""
    data = await get_main_channel_data(main_id)
    if not data:
        return
    
    posted_messages = data.get("posted_messages", [])
    
    if not posted_messages:
        print(f"⚠️ No messages to promote from {main_id}")
        return
    
    # Get current index
    current_index = data.get("current_post_index", 0)
    
    # Reset index if it exceeds list length
    if current_index >= len(posted_messages):
        current_index = 0
    
    # Get the message to promote
    msg_id = posted_messages[current_index]
    
    # Update index for next run (cycle through)
    next_index = (current_index + 1) % len(posted_messages)
    await apauthdb.update_one(
        {"chat_id": str(main_id)},
        {"$set": {"current_post_index": next_index}}
    )
    
    try:
        main_msg = await app.get_messages(main_id, msg_id)
        
        if not main_msg:
            print(f"❌ Message {msg_id} not found in {main_id}")
            return
        
        new_promo_posts = {}
        success_count = 0
        
        for promo_id_str in promo_channels:
            promo_id = int(promo_id_str)
            
            try:
                if forward_tag:
                    sent = await main_msg.forward(promo_id)
                else:
                    sent = await main_msg.copy(promo_id)
                
                new_promo_posts[promo_id_str] = [sent.id]
                success_count += 1
                print(f"✅ Sent post #{current_index + 1}/{len(posted_messages)} to {promo_id}")
                
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Failed to send to {promo_id}: {e}")
        
        await apauthdb.update_one(
            {"chat_id": str(main_id)},
            {"$set": {"active_promo_posts": new_promo_posts}}
        )
        
        print(f"🔄 Promoted to {success_count}/{len(promo_channels)} channels. Next: post #{next_index + 1}")
        
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
                await asyncio.sleep(60)
                continue
            
            if await should_run_promo(main_id):
                print(f"🔄 Running promo for {main_id}")
                
                await delete_old_posts(main_id, promo_channels)
                await send_new_posts(main_id, promo_channels, forward_tag)
                await update_last_promo_time(main_id)
            
            await asyncio.sleep(interval)
            
        except asyncio.CancelledError:
            print(f"❌ Promo loop cancelled for {main_id}")
            break
        except Exception as e:
            print(f"❌ Error in promo_loop: {e}")
            await asyncio.sleep(60)

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
    """
    Add main channel (where posts will be stored and promoted from)
    Usage: /apauth OR /apauth <channel_id> OR reply to channel message
    """
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
            return await message.reply_text(f"❌ Invalid channel! Error: {e}")
    
    if not chat_id:
        return await message.reply_text(
            "❌ Usage:\n"
            "/apauth <channel_id>\n\n"
            "OR reply to main channel message"
        )
    
    try:
        await client.get_chat_member(chat_id, "me")
        chat = await client.get_chat(chat_id)
    except Exception as e:
        return await message.reply_text(f"⚠️ Error: {e}")
    
    await add_main_channel(chat_id)
    await start_promo_task(chat_id)
    
    await message.reply_text(
        f"✅ Main Channel Authorized!\n\n"
        f"📌 Name: {chat.title}\n"
        f"🆔 ID: {chat_id}\n"
        f"🔄 Forward Tag: ON\n"
        f"⏱️ Interval: 5h\n\n"
        f"💡 Posts from this channel will be stored automatically\n"
        f"💡 Now add promo channels using /apc -b"
    )

@app.on_message(filters.command(["rmapauth"]))
async def remove_main_promo_channel(client, message: Message):
    """
    Remove main channel authorization
    Usage: /rmapauth <channel_id> OR reply to main channel message
    """
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
            return await message.reply_text(f"❌ Invalid channel! Error: {e}")
    
    if not chat_id:
        return await message.reply_text(
            "❌ Usage:\n"
            "/rmapauth <channel_id>\n\n"
            "OR reply to main channel message"
        )
    
    # Check if it's a main channel
    if not await is_main_channel(chat_id):
        return await message.reply_text("❌ This channel is not authorized as main channel!")
    
    try:
        chat = await client.get_chat(chat_id)
        channel_name = chat.title
    except:
        channel_name = str(chat_id)
    
    success = await remove_main_channel(chat_id)
    
    if success:
        await message.reply_text(
            f"✅ Main Channel Removed!\n\n"
            f"📌 Channel: {channel_name}\n"
            f"🆔 ID: {chat_id}\n\n"
            f"🛑 Background task stopped\n"
            f"🗑️ All data cleared from database"
        )
    else:
        await message.reply_text("❌ Failed to remove channel!")

@app.on_message(filters.command(["addpromochnl", "apc"]))
async def add_promo_channels_cmd(client, message: Message):
    """
    Add promo channels (where posts will be promoted to)
    
    Usage:
    1. Forward main channel message (top)
    2. Forward all promo channel messages below (100+)
    3. Reply to main channel message: /apc -b
    """
    
    is_bulk = "-b" in message.text
    
    if not message.reply_to_message:
        return await message.reply_text(
            "❌ Usage:\n\n"
            "1️⃣ Forward MAIN channel message (top)\n"
            "2️⃣ Forward PROMO channel messages below\n"
            "3️⃣ Reply to main channel message: /apc -b\n\n"
            "Bot will auto-detect all promo channels!"
        )
    
    # Get main channel from reply
    if not message.reply_to_message.forward_from_chat:
        return await message.reply_text("❌ Reply to a forwarded channel message!")
    
    main_id = message.reply_to_message.forward_from_chat.id
    
    # Check if main channel is authorized
    if not await is_main_channel(main_id):
        return await message.reply_text(
            f"❌ Channel {main_id} is not a main channel!\n\n"
            "First use: /apauth (reply to main channel message)"
        )
    
    if not is_bulk:
        return await message.reply_text(
            "❌ Use /apc -b for adding promo channels\n\n"
            "This will detect all forwarded channels below main channel"
        )
    
    # Collect all forwarded channel messages below
    promo_ids = []
    start_msg_id = message.reply_to_message.id
    
    status_msg = await message.reply_text("🔍 Detecting promo channels...")
    
    try:
        for i in range(1, 201):
            try:
                next_msg = await client.get_messages(message.chat.id, start_msg_id + i)
                
                if next_msg and next_msg.forward_from_chat:
                    promo_channel_id = next_msg.forward_from_chat.id
                    
                    # Don't add main channel to promo list
                    if promo_channel_id != main_id and promo_channel_id not in promo_ids:
                        promo_ids.append(promo_channel_id)
                        
                        # Update status every 10 channels
                        if len(promo_ids) % 10 == 0:
                            await status_msg.edit(f"🔍 Detected {len(promo_ids)} channels...")
                else:
                    # Stop if non-forwarded message found
                    if next_msg and not next_msg.forward_from_chat:
                        break
                        
            except Exception:
                break
                
    except Exception as e:
        print(f"Error collecting channels: {e}")
    
    if not promo_ids:
        await status_msg.edit("❌ No promo channels found below main channel message!")
        return
    
    # Add to database
    success = await add_promo_channels(main_id, promo_ids)
    
    if success:
        await status_msg.edit(
            f"✅ Added {len(promo_ids)} promo channels!\n\n"
            f"📌 Main Channel: {main_id}\n"
            f"📢 Promo Channels: {len(promo_ids)}\n"
            f"⏱️ Interval: 5h\n\n"
            f"💡 Posts will cycle automatically!"
        )
    else:
        await status_msg.edit("❌ Failed to add channels!")

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
            "❌ Usage:\n"
            "/rmpc <main_id> <promo_id>\n\n"
            "OR /rmpc <main_id> + reply to promo channel"
        )
    
    success = await remove_promo_channel(main_id, promo_id)
    
    if success:
        await message.reply_text(
            f"✅ Removed promo channel!\n\n"
            f"🗑️ Removed: {promo_id}\n"
            f"📌 From: {main_id}"
        )
    else:
        await message.reply_text("❌ Channel not found!")

@app.on_message(filters.command(["apset"]))
async def update_promo_settings_cmd(client, message: Message):
    """
    Update OR create promo settings
    If channel not authorized, it will create new entry
    If already exists, it will update settings
    """
    
    args = message.text.split()
    chat_id = None
    forward_tag = None
    interval = None
    
    # Get channel ID
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
            "❌ Usage:\n"
            "/apset <channel_id> -f on/off -t 5h\n\n"
            "Flags:\n"
            "-f : Forward tag (on/off)\n"
            "-t : Interval (5h/5d/5m)\n\n"
            "💡 Creates new entry if channel not authorized\n"
            "💡 Updates existing settings if already authorized"
        )
    
    # Parse flags
    if "-f" in args:
        idx = args.index("-f")
        if idx + 1 < len(args):
            forward_tag = args[idx + 1].lower() in ["on", "true", "1"]
    
    if "-t" in args:
        idx = args.index("-t")
        if idx + 1 < len(args):
            interval = args[idx + 1]
    
    # Check if no flags provided
    if forward_tag is None and interval is None:
        return await message.reply_text(
            "❌ Please provide at least one flag:\n\n"
            "-f on/off (forward tag)\n"
            "-t 5h/5d/5m (interval)"
        )
    
    # Check if channel exists in DB
    is_existing = await is_main_channel(chat_id)
    
    # Update or create
    success = await update_or_create_promo_settings(chat_id, forward_tag, interval)
    
    if success:
        # Get current settings
        data = await get_main_channel_data(chat_id)
        current_tag = data.get("forward_tag", True)
        current_interval = data.get("promo_interval", "5h")
        
        try:
            chat = await client.get_chat(chat_id)
            channel_name = chat.title
        except:
            channel_name = str(chat_id)
        
        action = "Updated" if is_existing else "Created"
        tag_status = "OFF" if not current_tag else "ON"
        
        await message.reply_text(
            f"✅ Settings {action}!\n\n"
            f"📌 Channel: {channel_name}\n"
            f"🆔 ID: {chat_id}\n"
            f"🔄 Forward Tag: {tag_status}\n"
            f"⏱️ Interval: {current_interval}\n\n"
            f"{'💡 Task restarted!' if is_existing else '💡 Task started!'}"
        )
    else:
        await message.reply_text("❌ Failed to update settings!")

@app.on_message(filters.command(["aplist"]))
async def list_promo_channels(client, message: Message):
    """List all main channels and their settings"""
    
    cursor = apauthdb.find({"is_main": True})
    channels = [doc async for doc in cursor]
    
    if not channels:
        return await message.reply_text("⚠️ No channels configured!")
    
    text = "✅ Auto Promo Channels:\n\n"
    
    for i, doc in enumerate(channels, start=1):
        chat_id = int(doc["chat_id"])
        promo_ids = doc.get("promo_channels", [])
        fwd_tag = "OFF" if not doc.get("forward_tag", True) else "ON"
        interval = doc.get("promo_interval", "5h")
        posted_count = len(doc.get("posted_messages", []))
        current_index = doc.get("current_post_index", 0)
        status = "🟢 Active" if chat_id in running_tasks else "🔴 Stopped"
        
        try:
            chat = await client.get_chat(chat_id)
            name = chat.title or "Unknown"
        except:
            name = "Unknown"
        
        text += f"{i}. {name}\n"
        text += f"   ├ ID: {chat_id}\n"
        text += f"   ├ Status: {status}\n"
        text += f"   ├ Promo: {len(promo_ids)} channels\n"
        text += f"   ├ Posts: {posted_count} stored\n"
        text += f"   ├ Current: #{current_index + 1}\n"
        text += f"   ├ Tag: {fwd_tag}\n"
        text += f"   └ Interval: {interval}\n\n"
    
    await message.reply_text(text)

# -------------------- MESSAGE HANDLER -------------------- #

@app.on_message(filters.channel & ~filters.service)
async def store_channel_messages(client, message: Message):
    """Auto-store messages from main channel"""
    
    if not await is_main_channel(message.chat.id):
        return
    
    await store_posted_message(message.chat.id, message.id)
    print(f"📝 Stored message {message.id} from {message.chat.id}")

# -------------------- STARTUP -------------------- #

async def load_existing_tasks():
    """Load and start tasks for existing main channels on bot restart"""
    await asyncio.sleep(3)  # Wait for bot to fully start
    
    cursor = apauthdb.find({"is_main": True, "is_active": True})
    channels = [doc async for doc in cursor]
    
    for doc in channels:
        chat_id = int(doc["chat_id"])
        await start_promo_task(chat_id)
        print(f"✅ Loaded task for channel {chat_id}")
    
    print(f"🚀 Loaded {len(channels)} auto-promo channels!")

# Start loading tasks on bot start
asyncio.create_task(load_existing_tasks())
print("🔥 Auto Promo system initialized!")
