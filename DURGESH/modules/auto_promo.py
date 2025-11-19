# auto_promo.py

import asyncio
from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatAdminRequired, UserNotParticipant, RPCError
from DURGESH import app
from DURGESH.database import db

apauthdb = db.apauth_channels

# Background task references
promo_task = None
cleanup_task = None

# Bulk mode collectors
bulk_add_active = {}
bulk_remove_active = {}
collected_channels = {}

# Helper: Parse time string
def parse_time(time_str):
    """Convert '5h', '30m', '2d' to seconds"""
    try:
        if time_str.endswith('m'):
            return int(time_str[:-1]) * 60
        elif time_str.endswith('h'):
            return int(time_str[:-1]) * 3600
        elif time_str.endswith('d'):
            return int(time_str[:-1]) * 86400
        return 18000
    except:
        return 18000

# Helper: Format seconds back to readable
def format_time(seconds):
    """Convert seconds to '5h', '30m', etc."""
    if seconds < 3600:
        return f"{seconds//60}m"
    elif seconds < 86400:
        return f"{seconds//3600}h"
    else:
        return f"{seconds//86400}d"

# Setup TTL indexes for auto cleanup
async def setup_ttl_indexes():
    """Setup MongoDB TTL indexes for automatic cleanup"""
    try:
        await apauthdb.create_index(
            [("created_at", 1)],
            expireAfterSeconds=2592000,  # 30 days
            partialFilterExpression={"post_type": "main_channel"},
            background=True
        )
        
        await apauthdb.create_index(
            [("posted_at", 1)],
            expireAfterSeconds=604800,  # 7 days
            partialFilterExpression={"post_type": "promo_track"},
            background=True
        )
        print("✅ TTL indexes ready")
    except Exception as e:
        print(f"⚠️ TTL error: {e}")

# Get or create config
async def get_config():
    config = await apauthdb.find_one({"_id": "config"})
    if not config:
        config = {
            "_id": "config",
            "main_channel": None,
            "promo_channels": [],
            "forward_tag": False,
            "promo_interval": 18000,
            "current_post_index": 0,
            "last_promo_time": None,
            "loop_running": False
        }
        await apauthdb.insert_one(config)
    return config

# Check if message still exists
async def message_exists(channel_id, message_id):
    """Check if a message exists in channel"""
    try:
        msg = await app.get_messages(channel_id, message_id)
        return msg and not msg.empty
    except:
        return False

# Track new posts from main channel
@app.on_message(filters.channel)
async def track_main_channel_posts(client, message: Message):
    """Automatically track posts from main channel"""
    try:
        config = await get_config()
        main_channel = config.get("main_channel")
        
        if main_channel and message.chat.id == main_channel:
            if message.text or message.media:
                await apauthdb.update_one(
                    {"_id": f"post_{message.id}"},
                    {"$set": {
                        "post_type": "main_channel",
                        "channel_id": message.chat.id,
                        "message_id": message.id,
                        "created_at": datetime.utcnow(),
                        "date": message.date,
                        "has_text": bool(message.text),
                        "has_media": bool(message.media),
                        "exists": True
                    }},
                    upsert=True
                )
    except Exception as e:
        print(f"❌ Track error: {e}")

# Global handler to collect forwarded channels in bulk mode
@app.on_message(filters.forwarded)
async def bulk_collector(client, message: Message):
    """Collect forwarded channels when bulk mode is active"""
    chat_id = message.chat.id
    
    if chat_id in bulk_add_active and bulk_add_active[chat_id]:
        if message.forward_from_chat:
            ch_id = message.forward_from_chat.id
            
            if chat_id not in collected_channels:
                collected_channels[chat_id] = {"add": [], "remove": []}
            
            try:
                member = await client.get_chat_member(ch_id, "me")
                if member.status in ["administrator", "creator"]:
                    collected_channels[chat_id]["add"].append(ch_id)
                    try:
                        await message.delete()
                    except:
                        pass
                else:
                    collected_channels[chat_id]["add"].append(None)
            except:
                collected_channels[chat_id]["add"].append(None)
    
    elif chat_id in bulk_remove_active and bulk_remove_active[chat_id]:
        if message.forward_from_chat:
            ch_id = message.forward_from_chat.id
            
            if chat_id not in collected_channels:
                collected_channels[chat_id] = {"add": [], "remove": []}
            
            collected_channels[chat_id]["remove"].append(ch_id)
            
            try:
                await message.delete()
            except:
                pass

# Auth main channel
@app.on_message(filters.command(["apauth"]))
async def auth_main_channel(client, message: Message):
    try:
        if message.reply_to_message:
            if message.reply_to_message.forward_from_chat:
                channel_id = message.reply_to_message.forward_from_chat.id
            else:
                return await message.reply("❌ Reply karo forwarded channel message ko!")
        elif len(message.command) > 1:
            try:
                channel_id = int(message.command[1])
            except:
                channel_id = message.command[1]
        else:
            return await message.reply("❌ Use: `/apauth <channel_id>` ya reply karo channel msg ko!")
        
        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {
                "main_channel": channel_id,
                "loop_running": True
            }},
            upsert=True
        )
        
        await message.reply(
            f"✅ Main channel auth ho gaya: `{channel_id}`\n\n"
            f"🚀 Bot ab automatically posts track karega!\n"
            f"⚠️ Bot ko channel me admin zaroor banao!"
        )
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Unauth main channel
@app.on_message(filters.command(["apunauth"]))
async def unauth_main_channel(client, message: Message):
    try:
        config = await get_config()
        old_channel = config.get("main_channel")
        
        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {
                "main_channel": None,
                "current_post_index": 0,
                "loop_running": False
            }},
            upsert=True
        )
        
        if old_channel:
            await apauthdb.delete_many({
                "channel_id": old_channel,
                "post_type": "main_channel"
            })
        
        await message.reply("✅ Main channel unauth ho gaya aur sab posts clear ho gaye!")
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Add promo channel
@app.on_message(filters.command(["addpromochnl", "apc"]))
async def add_promo_channel(client, message: Message):
    try:
        chat_id = message.chat.id
        
        if "-b" in message.text:
            bulk_add_active[chat_id] = True
            collected_channels[chat_id] = {"add": [], "remove": []}
            
            await message.reply(
                "📥 **Bulk Add Mode Active!**\n\n"
                "Abhi 1 minute hai! Channels forward karo yahan! ⏳"
            )
            
            await asyncio.sleep(60)
            
            bulk_add_active[chat_id] = False
            
            config = await get_config()
            existing = set(config.get("promo_channels", []))
            
            added = 0
            failed = 0
            
            for ch_id in collected_channels[chat_id]["add"]:
                if ch_id is None:
                    failed += 1
                elif ch_id not in existing:
                    existing.add(ch_id)
                    added += 1
            
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_channels": list(existing)}},
                upsert=True
            )
            
            del collected_channels[chat_id]
            
            await message.reply(
                f"✅ **Bulk Add Complete!**\n\n"
                f"✅ Added: {added}\n"
                f"❌ Failed: {failed}\n"
                f"📊 Total: {len(existing)}"
            )
            return
        
        if message.reply_to_message:
            if message.reply_to_message.forward_from_chat:
                channel_id = message.reply_to_message.forward_from_chat.id
            else:
                return await message.reply("❌ Reply karo forwarded channel message ko!")
        elif len(message.command) > 1:
            try:
                channel_id = int(message.command[1])
            except:
                channel_id = message.command[1]
        else:
            return await message.reply("❌ Use: `/apc <channel_id>` ya reply karo, ya `/apc -b` bulk ke liye!")
        
        config = await get_config()
        promo_channels = config.get("promo_channels", [])
        
        if channel_id not in promo_channels:
            promo_channels.append(channel_id)
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_channels": promo_channels}},
                upsert=True
            )
            await message.reply(f"✅ Promo channel add ho gaya: `{channel_id}`")
        else:
            await message.reply(f"ℹ️ Yeh channel already promo list mein hai!")
            
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Remove promo channel
@app.on_message(filters.command(["rmaddpromochnl", "rmapc"]))
async def remove_promo_channel(client, message: Message):
    try:
        chat_id = message.chat.id
        
        if "-b" in message.text:
            bulk_remove_active[chat_id] = True
            collected_channels[chat_id] = {"add": [], "remove": []}
            
            await message.reply(
                "🗑️ **Bulk Remove Mode Active!**\n\n"
                "Abhi 1 minute hai! Channels forward karo!"
            )
            
            await asyncio.sleep(60)
            
            bulk_remove_active[chat_id] = False
            
            config = await get_config()
            promo_channels = set(config.get("promo_channels", []))
            removed = 0
            
            for ch_id in collected_channels[chat_id]["remove"]:
                if ch_id in promo_channels:
                    promo_channels.remove(ch_id)
                    removed += 1
            
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_channels": list(promo_channels)}},
                upsert=True
            )
            
            del collected_channels[chat_id]
            
            await message.reply(
                f"✅ **Bulk Remove Complete!**\n\n"
                f"🗑️ Removed: {removed}\n"
                f"📊 Remaining: {len(promo_channels)}"
            )
            return
        
        if message.reply_to_message:
            if message.reply_to_message.forward_from_chat:
                channel_id = message.reply_to_message.forward_from_chat.id
            else:
                return await message.reply("❌ Reply karo forwarded channel message ko!")
        elif len(message.command) > 1:
            try:
                channel_id = int(message.command[1])
            except:
                channel_id = message.command[1]
        else:
            return await message.reply("❌ Use: `/rmapc <channel_id>` ya reply karo!")
        
        config = await get_config()
        promo_channels = config.get("promo_channels", [])
        
        if channel_id in promo_channels:
            promo_channels.remove(channel_id)
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_channels": promo_channels}},
                upsert=True
            )
            await message.reply(f"✅ Promo channel remove ho gaya: `{channel_id}`")
        else:
            await message.reply(f"ℹ️ Yeh channel promo list mein nahi hai!")
            
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Set config
@app.on_message(filters.command(["set"]))
async def set_config(client, message: Message):
    try:
        args = message.text.split()
        config = await get_config()
        
        forward_tag = config.get("forward_tag", False)
        promo_interval = config.get("promo_interval", 18000)
        
        if len(args) == 1:
            return await message.reply(
                f"⚙️ **Current Settings**\n\n"
                f"🏷️ Forward Tag: `{'On' if forward_tag else 'Off'}`\n"
                f"⏰ Promo Interval: `{format_time(promo_interval)}`\n\n"
                f"**Usage:**\n"
                f"`/set -f on/off -t 5h`"
            )
        
        if "-f" in args:
            idx = args.index("-f")
            if len(args) > idx + 1:
                val = args[idx + 1].lower()
                forward_tag = val == "on"
        
        if "-t" in args:
            idx = args.index("-t")
            if len(args) > idx + 1:
                promo_interval = parse_time(args[idx + 1])
        
        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {
                "forward_tag": forward_tag,
                "promo_interval": promo_interval
            }},
            upsert=True
        )
        
        await message.reply(
            f"✅ **Settings Updated**\n\n"
            f"🏷️ Forward Tag: `{'On' if forward_tag else 'Off'}`\n"
            f"⏰ Promo Interval: `{format_time(promo_interval)}`"
        )
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Cleanup orphaned/deleted posts
async def cleanup_deleted_posts():
    """Periodically check and remove deleted posts from DB"""
    while True:
        try:
            posts = []
            async for post in apauthdb.find({"post_type": "main_channel", "exists": True}):
                posts.append(post)
            
            deleted_count = 0
            for post in posts:
                channel_id = post.get("channel_id")
                message_id = post.get("message_id")
                
                if not await message_exists(channel_id, message_id):
                    await apauthdb.update_one(
                        {"_id": post["_id"]},
                        {"$set": {"exists": False}}
                    )
                    deleted_count += 1
                
                await asyncio.sleep(1)
            
            if deleted_count > 0:
                print(f"🧹 Cleaned {deleted_count} deleted posts")
            
            cutoff_date = datetime.utcnow() - timedelta(days=7)
            result = await apauthdb.delete_many({
                "post_type": "promo_track",
                "posted_at": {"$lt": cutoff_date}
            })
            
            if result.deleted_count > 0:
                print(f"🧹 Cleaned {result.deleted_count} old promo records")
            
            await asyncio.sleep(21600)  # 6 hours
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Cleanup error: {e}")
            await asyncio.sleep(3600)

# Background promo loop
async def promo_loop():
    """Main background loop for auto promotion"""
    print("🚀 Promo loop started")
    
    await apauthdb.update_one(
        {"_id": "config"},
        {"$set": {"loop_running": True}},
        upsert=True
    )
    
    while True:
        try:
            config = await get_config()
            
            if not config.get("loop_running", False):
                await asyncio.sleep(120)
                continue
            
            main_channel = config.get("main_channel")
            promo_channels = config.get("promo_channels", [])
            forward_tag = config.get("forward_tag", False)
            promo_interval = config.get("promo_interval", 18000)
            current_index = config.get("current_post_index", 0)
            
            if not main_channel or not promo_channels:
                await asyncio.sleep(120)
                continue
            
            posts_data = []
            async for post_doc in apauthdb.find({
                "channel_id": main_channel,
                "post_type": "main_channel",
                "exists": {"$ne": False}
            }).sort("date", -1).limit(50):
                posts_data.append(post_doc)
            
            if not posts_data:
                await asyncio.sleep(300)
                continue
            
            if current_index >= len(posts_data):
                current_index = 0
            
            current_post_data = posts_data[current_index]
            message_id = current_post_data.get("message_id")
            
            try:
                if not await message_exists(main_channel, message_id):
                    await apauthdb.update_one(
                        {"_id": current_post_data["_id"]},
                        {"$set": {"exists": False}}
                    )
                    current_index = (current_index + 1) % len(posts_data)
                    await apauthdb.update_one(
                        {"_id": "config"},
                        {"$set": {"current_post_index": current_index}},
                        upsert=True
                    )
                    await asyncio.sleep(5)
                    continue
                
                current_post = await app.get_messages(main_channel, message_id)
                
            except Exception as e:
                await apauthdb.update_one(
                    {"_id": current_post_data["_id"]},
                    {"$set": {"exists": False}}
                )
                current_index = (current_index + 1) % len(posts_data)
                await apauthdb.update_one(
                    {"_id": "config"},
                    {"$set": {"current_post_index": current_index}},
                    upsert=True
                )
                await asyncio.sleep(10)
                continue
            
            success_count = 0
            fail_count = 0
            
            for channel_id in promo_channels:
                try:
                    last_msg_data = await apauthdb.find_one({
                        "promo_channel_id": channel_id,
                        "post_type": "promo_track"
                    })
                    
                    if last_msg_data and last_msg_data.get("last_msg_id"):
                        try:
                            await app.delete_messages(channel_id, last_msg_data["last_msg_id"])
                        except:
                            pass
                    
                    if forward_tag:
                        sent = await current_post.forward(channel_id)
                    else:
                        sent = await current_post.copy(channel_id)
                    
                    await apauthdb.update_one(
                        {"promo_channel_id": channel_id},
                        {"$set": {
                            "post_type": "promo_track",
                            "last_msg_id": sent.id,
                            "posted_at": datetime.utcnow(),
                            "source_msg_id": message_id
                        }},
                        upsert=True
                    )
                    
                    success_count += 1
                    await asyncio.sleep(2)
                    
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    fail_count += 1
                except Exception:
                    fail_count += 1
            
            print(f"✅ Promo done: {success_count} success, {fail_count} failed")
            
            current_index = (current_index + 1) % len(posts_data)
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {
                    "current_post_index": current_index,
                    "last_promo_time": datetime.utcnow()
                }},
                upsert=True
            )
            
            await asyncio.sleep(promo_interval)
            
        except asyncio.CancelledError:
            print("🛑 Promo loop stopped")
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"loop_running": False}},
                upsert=True
            )
            break
        except Exception as e:
            print(f"❌ Loop error: {e}")
            await asyncio.sleep(120)


# Startup handler
async def start_promo_on_boot():
    """Start promo loop when bot boots up"""
    global promo_task, cleanup_task
    
    await asyncio.sleep(5)
    
    await setup_ttl_indexes()
    
    config = await get_config()
    main_channel = config.get("main_channel")
    promo_channels = config.get("promo_channels", [])
    
    # Show only useful info
    if main_channel:
        print(f"📢 Main Channel: {main_channel}")
        print(f"📊 Promo Channels: {len(promo_channels)}")
    else:
        print("⚠️ Main channel not set")
    
    promo_task = asyncio.create_task(promo_loop())
    cleanup_task = asyncio.create_task(cleanup_deleted_posts())

# Create startup task
asyncio.create_task(start_promo_on_boot())
