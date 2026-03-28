# auto_promo.py - Final Stable Version (No Data Loss)
import asyncio
from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatAdminRequired, UserNotParticipant, RPCError
from DURGESH import app
from DURGESH.database import db

apauthdb = db.apauth_channels

promo_task = None
cleanup_task = None
force_promo_event = asyncio.Event()

bulk_add_active = {}
bulk_remove_active = {}
collected_channels = {}

# ────────────────────────────────────────────────
# Helper Functions
# ────────────────────────────────────────────────
def parse_time(time_str):
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

def format_time(seconds):
    if seconds < 3600:
        return f"{seconds//60}m"
    elif seconds < 86400:
        return f"{seconds//3600}h"
    else:
        return f"{seconds//86400}d"

async def setup_ttl_indexes():
    try:
        await apauthdb.create_index(
            [("created_at", 1)],
            expireAfterSeconds=2592000,
            partialFilterExpression={"post_type": "main_channel"},
            background=True
        )
        await apauthdb.create_index(
            [("posted_at", 1)],
            expireAfterSeconds=604800,
            partialFilterExpression={"post_type": "promo_track"},
            background=True
        )
        await apauthdb.create_index(
            [("post_number", 1)],
            background=True
        )
    except Exception as e:
        print(f"⚠️ TTL error: {e}")

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
            "loop_running": False,
            "promo_enabled": True,
            "total_posts_tracked": 0
        }
        await apauthdb.insert_one(config)
    elif "promo_enabled" not in config:
        await apauthdb.update_one({"_id": "config"}, {"$set": {"promo_enabled": True}})
        config["promo_enabled"] = True
    return config

async def message_exists(channel_id, message_id):
    try:
        msg = await app.get_messages(channel_id, message_id)
        return msg and not msg.empty
    except:
        return False

async def get_bot_status(channel_id):
    try:
        member = await app.get_chat_member(channel_id, "me")
        return member.status
    except Exception as e:
        return f"Error: {e}"

async def get_next_post_number():
    """Get next sequential post number"""
    last_post = await apauthdb.find_one(
        {"post_type": "main_channel"},
        sort=[("post_number", -1)]
    )
    if last_post:
        return last_post.get("post_number", 0) + 1
    return 1

# ────────────────────────────────────────────────
# Track Main Channel Posts
# ────────────────────────────────────────────────
@app.on_message(filters.channel)
async def track_main_channel_posts(client, message: Message):
    try:
        config = await get_config()
        main_channel = config.get("main_channel")
        
        if main_channel and message.chat.id == main_channel:
            if message.text or message.media:
                doc_id = f"post_{message.chat.id}_{message.id}"
                
                # Check if already tracked
                existing = await apauthdb.find_one({"_id": doc_id})
                if existing:
                    print(f"ℹ️ Already tracked: {doc_id}")
                    return
                
                # Get sequential post number
                post_number = await get_next_post_number()
                
                await apauthdb.update_one(
                    {"_id": doc_id},
                    {"$set": {
                        "post_type": "main_channel",
                        "channel_id": message.chat.id,
                        "message_id": message.id,
                        "post_number": post_number,
                        "created_at": datetime.utcnow(),
                        "date": message.date,
                        "has_text": bool(message.text),
                        "has_media": bool(message.media),
                        "exists": True,
                        "promo_count": 0
                    }},
                    upsert=True
                )
                
                # Update total count in config
                await apauthdb.update_one(
                    {"_id": "config"},
                    {"$inc": {"total_posts_tracked": 1}}
                )
                
                try:
                    await message.react(emoji="👍")
                except:
                    pass
                print(f"✅ Tracked #{post_number}: {doc_id}")
    except Exception as e:
        print(f"❌ Track error: {e}")

# ────────────────────────────────────────────────
# Bulk Collector
# ────────────────────────────────────────────────
@app.on_message(filters.forwarded)
async def bulk_collector(client, message: Message):
    chat_id = message.chat.id
    
    if chat_id in bulk_add_active and bulk_add_active[chat_id]:
        if message.forward_from_chat:
            ch_id = message.forward_from_chat.id
            if chat_id not in collected_channels:
                collected_channels[chat_id] = {"add": [], "remove": []}
            try:
                member = await client.get_chat_member(ch_id, "me")
                status_str = str(member.status).split('.')[-1].lower()
                if status_str in ["administrator", "creator", "owner"]:
                    collected_channels[chat_id]["add"].append(ch_id)
                else:
                    collected_channels[chat_id]["add"].append(None)
            except:
                collected_channels[chat_id]["add"].append(None)
            try:
                await message.delete()
            except:
                pass
                
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

# ────────────────────────────────────────────────
# ON/OFF Toggle Commands
# ────────────────────────────────────────────────
@app.on_message(filters.command(["promo", "promotoggle"]))
async def toggle_promo(client, message: Message):
    try:
        args = message.text.split()
        config = await get_config()
        
        if len(args) < 2:
            state = "ON" if config.get("promo_enabled", True) else "OFF"
            return await message.reply(
                f"🎛️ **Promo System**\n\n"
                f"Current State: `{state}`\n\n"
                f"Usage: `/promo on` | `/promo off`"
            )
        
        action = args[1].lower()
        
        if action == "on":
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_enabled": True, "loop_running": True}},
                upsert=True
            )
            await message.reply("✅ **Promo System ENABLED**\n\n🔄 Loop restart ho raha hai...")
            print("🔛 Promo system enabled by user")
            
        elif action == "off":
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_enabled": False, "loop_running": False}},
                upsert=True
            )
            
            progress_msg = await message.reply("🛑 **Promo System DISABLED**\n\n⏳ Starting cleanup...")
            
            deleted_count = 0
            failed_count = 0
            skipped_count = 0
            
            promo_entries = []
            async for entry in apauthdb.find({"post_type": "promo_track"}):
                if entry.get("promo_channel_id") and entry.get("last_msg_id"):
                    promo_entries.append({
                        "channel_id": entry["promo_channel_id"],
                        "message_id": entry["last_msg_id"]
                    })
            
            total = len(promo_entries)
            
            if total > 0:
                await progress_msg.edit_text(f"🗑️ Cleaning {total} promo posts from channels...")
                
                for i, entry in enumerate(promo_entries, 1):
                    try:
                        await app.delete_messages(
                            chat_id=entry["channel_id"],
                            message_ids=entry["message_id"],
                            revoke=True
                        )
                        deleted_count += 1
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                        try:
                            await app.delete_messages(
                                chat_id=entry["channel_id"],
                                message_ids=entry["message_id"],
                                revoke=True
                            )
                            deleted_count += 1
                        except:
                            failed_count += 1
                    except ChatAdminRequired:
                        skipped_count += 1
                    except UserNotParticipant:
                        skipped_count += 1
                    except RPCError as e:
                        if "BOT_METHOD_INVALID" in str(e):
                            skipped_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        failed_count += 1
                    
                    if i % 10 == 0 or i == total:
                        try:
                            await progress_msg.edit_text(
                                f"🛑 **Promo System DISABLED**\n\n"
                                f"🗑️ Progress: `{i}/{total}`\n"
                                f"✅ Deleted: `{deleted_count}`\n"
                                f"❌ Failed: `{failed_count}`\n"
                                f"⚠️ Skipped: `{skipped_count}`"
                            )
                        except:
                            pass
                    await asyncio.sleep(0.3)
            else:
                await progress_msg.edit_text("📭 No DB records found.")
            
            await apauthdb.delete_many({"post_type": "promo_track"})
            
            final_report = (
                f"🛑 **Promo System DISABLED**\n\n"
                f"🗑️ **Cleanup Complete**\n\n"
                f"✅ Messages Deleted: `{deleted_count}`\n"
                f"❌ Failed: `{failed_count}`\n"
                f"⚠️ Skipped: `{skipped_count}`\n\n"
                f"💡 Use `/promo on` to restart fresh"
            )
            try:
                await progress_msg.edit_text(final_report)
            except:
                await message.reply(final_report)
                
            print(f"🔌 Promo OFF: {deleted_count} deleted, {failed_count} failed, {skipped_count} skipped")
            
        else:
            await message.reply("❌ Invalid option. Use: `/promo on` or `/promo off`")
            
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ────────────────────────────────────────────────
# Status Command (With DB Debug Info)
# ────────────────────────────────────────────────
@app.on_message(filters.command(["apstatus"]))
async def check_status(client, message: Message):
    try:
        config = await get_config()
        main_channel = config.get("main_channel")
        promo_channels = config.get("promo_channels", [])
        
        status_msg = "🔍 **Auto Promo Status**\n\n"
        
        promo_state = "🟢 ON" if config.get("promo_enabled", True) else "🔴 OFF"
        status_msg += f"⚡ System: `{promo_state}`\n\n"
        
        if main_channel:
            status_msg += f"📢 Main Channel: `{main_channel}`\n"
            bot_status = await get_bot_status(main_channel)
            status_msg += f"🤖 Bot Status: `{bot_status}`\n\n"
            
            # ✅ Multiple query attempts for debugging
            post_count_strict = await apauthdb.count_documents({
                "channel_id": main_channel,
                "post_type": "main_channel",
                "exists": True
            })
            
            post_count_loose = await apauthdb.count_documents({
                "channel_id": main_channel,
                "post_type": "main_channel"
            })
            
            status_msg += f"📝 Tracked Posts (Strict): `{post_count_strict}`\n"
            status_msg += f"📝 Tracked Posts (All): `{post_count_loose}`\n\n"
            
            # Show last 5 posts with numbers
            status_msg += "📊 **Recent Posts:**\n"
            async for post in apauthdb.find(
                {"channel_id": main_channel, "post_type": "main_channel"},
                sort=[("post_number", -1)]
            ).limit(5):
                exists_val = post.get('exists', 'N/A')
                status_msg += f"  #{post.get('post_number', '?')} | Msg: `{post.get('message_id')}` | Exists: `{exists_val}`\n"
            status_msg += "\n"
        else:
            status_msg += "📢 Main Channel: `Not Set`\n\n"
            
        status_msg += f"📊 Promo Channels: `{len(promo_channels)}`\n"
        status_msg += f"⏰ Interval: `{format_time(config.get('promo_interval', 18000))}`\n"
        status_msg += f"🏷️ Forward Tag: `{'On' if config.get('forward_tag') else 'Off'}`\n"
        status_msg += f"🔄 Loop Running: `{'Yes' if config.get('loop_running') else 'No'}`\n"
        status_msg += f"📍 Current Index: `{config.get('current_post_index', 0)}`\n"
        status_msg += f"📈 Total Tracked: `{config.get('total_posts_tracked', 0)}`"
        
        await message.reply(status_msg)
    except Exception as e:
        await message.reply(f"❌ Error: {e}")

# ────────────────────────────────────────────────
# Auth/Unauth Main Channel
# ────────────────────────────────────────────────
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
            return await message.reply("❌ Use: `/apauth <channel_id>` ya reply karo")
        
        try:
            chat = await app.get_chat(channel_id)
        except Exception as e:
            return await message.reply(f"❌ Channel access failed: `{e}`")
        
        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {"main_channel": channel_id, "loop_running": True}},
            upsert=True
        )
        
        await message.reply(
            f"✅ Main channel set: `{chat.title}`\n"
            f"🆔 ID: `{channel_id}`\n\n"
            f"📝 Channel me post karo, bot 👍 react karega!"
        )
        print(f"📢 Main channel set: {channel_id}")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@app.on_message(filters.command(["apunauth"]))
async def unauth_main_channel(client, message: Message):
    try:
        config = await get_config()
        old_channel = config.get("main_channel")
        
        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {"main_channel": None, "current_post_index": 0, "loop_running": False, "total_posts_tracked": 0}},
            upsert=True
        )
        
        if old_channel:
            await apauthdb.delete_many({
                "channel_id": old_channel,
                "post_type": "main_channel"
            })
        
        await message.reply("✅ Main channel unauth!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ────────────────────────────────────────────────
# Add Promo Channel
# ────────────────────────────────────────────────
@app.on_message(filters.command(["addpromochnl", "apc"]))
async def add_promo_channel(client, message: Message):
    try:
        chat_id = message.chat.id
        
        if "-b" in message.text:
            bulk_add_active[chat_id] = True
            collected_channels[chat_id] = {"add": [], "remove": []}
            await message.reply("📥 Bulk Add! 1 min - Forward karo! ⏳")
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
            await message.reply(f"✅ Bulk Done!\n\n✅ Added: {added}\n❌ Failed: {failed}\n📊 Total: {len(existing)}")
            return
        
        if message.reply_to_message:
            if message.reply_to_message.forward_from_chat:
                channel_id = message.reply_to_message.forward_from_chat.id
            else:
                return await message.reply("❌ Reply karo forwarded msg!")
        elif len(message.command) > 1:
            try:
                channel_id = int(message.command[1])
            except:
                channel_id = message.command[1]
        else:
            return await message.reply("❌ Use: `/apc <id>` ya `/apc -b`")
        
        try:
            chat = await app.get_chat(channel_id)
            member = await app.get_chat_member(channel_id, "me")
            status_str = str(member.status).split('.')[-1].lower()
            
            if status_str not in ["administrator", "creator", "owner"]:
                return await message.reply(f"❌ Bot is {member.status}\n\n⚠️ Bot ko Admin banao!")
            if member.privileges and not member.privileges.can_post_messages:
                return await message.reply(f"⚠️ Bot admin hai but Post Messages permission nahi!\n\n✅ Permission enable karo")
        except Exception as e:
            return await message.reply(f"❌ Check failed: `{str(e)}`")
        
        config = await get_config()
        promo_channels = config.get("promo_channels", [])
        
        if channel_id not in promo_channels:
            promo_channels.append(channel_id)
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_channels": promo_channels}},
                upsert=True
            )
            await message.reply(f"✅ Added!\n\n📢 {chat.title}\n📊 Total: {len(promo_channels)}")
        else:
            await message.reply("ℹ️ Already added!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ────────────────────────────────────────────────
# Remove Promo Channel
# ────────────────────────────────────────────────
@app.on_message(filters.command(["rmaddpromochnl", "rmapc"]))
async def remove_promo_channel(client, message: Message):
    try:
        chat_id = message.chat.id
        
        if "-b" in message.text:
            bulk_remove_active[chat_id] = True
            collected_channels[chat_id] = {"add": [], "remove": []}
            await message.reply("🗑️ Bulk Remove! 1 min")
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
            await message.reply(f"✅ Done!\n\n🗑️ Removed: {removed}\n📊 Remaining: {len(promo_channels)}")
            return
        
        if message.reply_to_message:
            if message.reply_to_message.forward_from_chat:
                channel_id = message.reply_to_message.forward_from_chat.id
            else:
                return await message.reply("❌ Reply karo forwarded msg!")
        elif len(message.command) > 1:
            try:
                channel_id = int(message.command[1])
            except:
                channel_id = message.command[1]
        else:
            return await message.reply("❌ Use: `/rmapc <id>`")
        
        config = await get_config()
        promo_channels = config.get("promo_channels", [])
        
        if channel_id in promo_channels:
            promo_channels.remove(channel_id)
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_channels": promo_channels}},
                upsert=True
            )
            await message.reply(f"✅ Removed: `{channel_id}`")
        else:
            await message.reply("ℹ️ Not in list!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ────────────────────────────────────────────────
# Set Config
# ────────────────────────────────────────────────
@app.on_message(filters.command(["set"]))
async def set_config(client, message: Message):
    try:
        args = message.text.split()
        config = await get_config()
        forward_tag = config.get("forward_tag", False)
        promo_interval = config.get("promo_interval", 18000)
        
        if len(args) == 1:
            return await message.reply(
                f"⚙️ **Settings**\n\n"
                f"🏷️ Forward Tag: `{'On' if forward_tag else 'Off'}`\n"
                f"⏰ Interval: `{format_time(promo_interval)}`\n\n"
                f"**Usage:** `/set -f on/off -t 5h`"
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
            {"$set": {"forward_tag": forward_tag, "promo_interval": promo_interval}},
            upsert=True
        )
        
        await message.reply(
            f"✅ **Updated**\n\n"
            f"🏷️ Forward Tag: `{'On' if forward_tag else 'Off'}`\n"
            f"⏰ Interval: `{format_time(promo_interval)}`"
        )
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ────────────────────────────────────────────────
# Force Promo Command
# ────────────────────────────────────────────────
@app.on_message(filters.command(["forcespromo", "fp", "fpromo"]))
async def force_start_promo(client, message: Message):
    try:
        config = await get_config()
        if not config.get("main_channel"):
            return await message.reply("❌ Main channel set nahi hai! Pehle `/apauth` use karo")
        if not config.get("promo_channels"):
            return await message.reply("❌ Promo channels nahi hain! Pehle `/apc` use karo")
        
        post_count = await apauthdb.count_documents({
            "channel_id": config.get("main_channel"),
            "post_type": "main_channel"
        })
        
        if post_count == 0:
            return await message.reply("❌ Koi post track nahi hai! Main channel me post karo pehle")
        
        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {"current_post_index": 0, "loop_running": True}},
            upsert=True
        )
        force_promo_event.set()
        
        await message.reply(
            "🔄 **Force Promo Triggered!**\n\n"
            "📍 Index reset to 0\n"
            f"📝 Total posts: {post_count}\n"
            "⚡ Immediate promo cycle starting..."
        )
        print("🔄 Force promo: Index=0, Immediate cycle triggered")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ────────────────────────────────────────────────
# Cleanup Task
# ────────────────────────────────────────────────
async def cleanup_deleted_posts():
    while True:
        try:
            posts = []
            async for post in apauthdb.find({"post_type": "main_channel"}):
                if post.get("exists", True) is not False:
                    posts.append(post)
            
            deleted = 0
            for post in posts:
                if not await message_exists(post.get("channel_id"), post.get("message_id")):
                    await apauthdb.update_one({"_id": post["_id"]}, {"$set": {"exists": False}})
                    deleted += 1
                await asyncio.sleep(1)
            
            if deleted > 0:
                print(f"🧹 Cleaned {deleted} posts")
            
            result = await apauthdb.delete_many({
                "post_type": "promo_track",
                "posted_at": {"$lt": datetime.utcnow() - timedelta(days=7)}
            })
            if result.deleted_count > 0:
                print(f"🧹 Cleaned {result.deleted_count} promos")
            
            await asyncio.sleep(21600)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Cleanup: {e}")
            await asyncio.sleep(3600)

# ────────────────────────────────────────────────
# MAIN PROMO LOOP (FIXED QUERY - NO DATA LOSS)
# ────────────────────────────────────────────────
async def promo_loop():
    print("🚀 Promo loop started")
    await apauthdb.update_one({"_id": "config"}, {"$set": {"loop_running": True}}, upsert=True)
    cycle = 0
    
    while True:
        try:
            config = await get_config()
            
            # Check if promo is enabled
            if not config.get("promo_enabled", True) or not config.get("loop_running", False):
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
            
            cycle += 1
            print(f"🔄 Cycle #{cycle}")
            
            # ✅ FIXED: Simple query without $or - fetch ALL posts first
            posts_data = []
            async for post_doc in apauthdb.find({
                "channel_id": main_channel,
                "post_type": "main_channel"
            }).sort("post_number", 1).limit(50):
                # ✅ Filter out only exists=False posts in Python (not DB)
                if post_doc.get("exists") is not False:
                    posts_data.append(post_doc)
            
            print(f"📊 Posts found: {len(posts_data)}")
            
            # ✅ Debug: Show total in DB vs filtered
            total_in_db = await apauthdb.count_documents({
                "channel_id": main_channel,
                "post_type": "main_channel"
            })
            print(f"🔍 DB Total: {total_in_db}, Filtered: {len(posts_data)}")
            
            if not posts_
                print("⚠️ No posts to promote, waiting...")
                await asyncio.sleep(300)
                continue
            
            # Safe index handling
            if current_index >= len(posts_data):
                current_index = 0
            
            message_id = posts_data[current_index].get("message_id")
            post_number = posts_data[current_index].get("post_number", "?")
            print(f"📤 Promoting post #{post_number} (ID: {message_id})")
            
            try:
                # Check if message exists
                if not await message_exists(main_channel, message_id):
                    print(f"⚠️ Post {message_id} deleted, marking as exists=False")
                    await apauthdb.update_one(
                        {"_id": posts_data[current_index]["_id"]},
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
                print(f"❌ Get post failed: {e}")
                await apauthdb.update_one(
                    {"_id": posts_data[current_index]["_id"]},
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
            
            success = 0
            failed = 0
            
            for channel_id in promo_channels:
                try:
                    # Delete last promo message if exists
                    last_msg = await apauthdb.find_one({
                        "promo_channel_id": channel_id,
                        "post_type": "promo_track"
                    })
                    if last_msg and last_msg.get("last_msg_id"):
                        try:
                            await app.delete_messages(channel_id, last_msg["last_msg_id"])
                        except:
                            pass
                    
                    # Send promo
                    sent = await current_post.forward(channel_id) if forward_tag else await current_post.copy(channel_id)
                    
                    # Track in DB
                    await apauthdb.update_one(
                        {"promo_channel_id": channel_id},
                        {"$set": {
                            "post_type": "promo_track",
                            "last_msg_id": sent.id,
                            "posted_at": datetime.utcnow(),
                            "source_msg_id": message_id,
                            "post_number": post_number
                        }},
                        upsert=True
                    )
                    
                    # Update promo count for this post
                    await apauthdb.update_one(
                        {"_id": posts_data[current_index]["_id"]},
                        {"$inc": {"promo_count": 1}}
                    )
                    
                    success += 1
                    await asyncio.sleep(2)
                    
                except FloodWait as e:
                    print(f"⏳ FloodWait: {e.value}s")
                    await asyncio.sleep(e.value)
                    failed += 1
                except Exception as e:
                    print(f"❌ Failed channel {channel_id}: {e}")
                    failed += 1
            
            print(f"✅ Done: {success} success, {failed} failed")
            
            # Move to next post
            current_index = (current_index + 1) % len(posts_data)
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {
                    "current_post_index": current_index,
                    "last_promo_time": datetime.utcnow()
                }},
                upsert=True
            )
            
            print(f"⏰ Next promo in {format_time(promo_interval)}")
            
            # Wait for interval or force trigger
            try:
                await asyncio.wait_for(force_promo_event.wait(), timeout=promo_interval)
                force_promo_event.clear()
                print("⚡ Force trigger activated - skipping wait")
            except asyncio.TimeoutError:
                pass
                
        except asyncio.CancelledError:
            print("🛑 Loop stopped")
            await apauthdb.update_one({"_id": "config"}, {"$set": {"loop_running": False}}, upsert=True)
            break
        except Exception as e:
            print(f"❌ Loop error: {e}")
            await asyncio.sleep(120)

# ────────────────────────────────────────────────
# Startup
# ────────────────────────────────────────────────
async def start_promo_on_boot():
    global promo_task, cleanup_task
    try:
        await asyncio.sleep(5)
        await setup_ttl_indexes()
        config = await get_config()
        main_channel = config.get("main_channel")
        promo_channels = config.get("promo_channels", [])
        
        if main_channel:
            print(f"📢 Main: {main_channel}")
            print(f"📊 Promo: {len(promo_channels)}")
        
        promo_task = asyncio.create_task(promo_loop())
        cleanup_task = asyncio.create_task(cleanup_deleted_posts())
    except Exception as e:
        print(f"❌ Startup: {e}")

asyncio.create_task(start_promo_on_boot())
