# zauto_promo.py
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

# Event to trigger immediate promo
force_promo_event = asyncio.Event()

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
            "loop_running": False,
            "is_active": True # Default ON rahega
        }
        await apauthdb.insert_one(config)
    
    # Agar is_active update nahi hai purane db me toh set kar do
    if "is_active" not in config:
        await apauthdb.update_one({"_id": "config"}, {"$set": {"is_active": True}})
        config["is_active"] = True
        
    return config

# Check if message still exists
async def message_exists(channel_id, message_id):
    """Check if a message exists in channel"""
    try:
        msg = await app.get_messages(channel_id, message_id)
        return msg and not msg.empty
    except:
        return False

# Get bot status in channel
async def get_bot_status(channel_id):
    """Get bot member status in channel"""
    try:
        member = await app.get_chat_member(channel_id, "me")
        return member.status
    except Exception as e:
        return f"Error: {e}"

# ----------------- TRACKING POSTS ----------------- #

@app.on_message(filters.channel & ~filters.forwarded)
async def track_main_channel_posts(client, message: Message):
    """Automatically track posts from main channel and react"""
    try:
        config = await get_config()
        main_channel = config.get("main_channel")
        
        # Check agar post main channel ki hi hai
        if main_channel and message.chat.id == main_channel:
            if message.text or message.media:
                # Unique ID fix: post_{channel_id}_{message_id}
                unique_id = f"post_{message.chat.id}_{message.id}"
                await apauthdb.update_one(
                    {"_id": unique_id},
                    {"$set": {
                        "post_type": "main_channel",
                        "channel_id": message.chat.id,
                        "message_id": message.id,
                        "created_at": datetime.utcnow(),
                        "date": message.date,
                        "has_text": bool(message.text or message.caption),
                        "has_media": bool(message.media),
                        "exists": True
                    }},
                    upsert=True
                )
                
                # React with 👍 to confirm DB add
                try:
                    await message.react(emoji="👍")
                except Exception:
                    pass
    except Exception as e:
        print(f"❌ Track error: {e}")

@app.on_message(filters.command(["addp"]))
async def manual_add_promo(client, message: Message):
    """Force add a post to database via reply"""
    try:
        config = await get_config()
        main_channel = config.get("main_channel")
        
        if not main_channel:
            return await message.reply("❌ Main channel set nahi hai! Pehle `/apauth` use karein.")
            
        if not message.reply_to_message:
            return await message.reply("❌ Kripya us message ka reply karein jise aap add karna chahte hain.")

        msg = message.reply_to_message
        msg_id_to_save = None

        # Fix: Ensure we are capturing the real message ID from the main channel
        if msg.forward_from_chat and msg.forward_from_chat.id == main_channel:
            msg_id_to_save = msg.forward_from_message_id
        elif message.chat.id == main_channel:
            msg_id_to_save = msg.id
        else:
            return await message.reply("❌ Ye message main channel se forward nahi kiya gaya hai!")

        unique_id = f"post_{main_channel}_{msg_id_to_save}"
        await apauthdb.update_one(
            {"_id": unique_id},
            {"$set": {
                "post_type": "main_channel",
                "channel_id": main_channel,
                "message_id": msg_id_to_save,
                "created_at": datetime.utcnow(),
                "has_text": bool(msg.text or msg.caption),
                "has_media": bool(msg.media),
                "exists": True
            }},
            upsert=True
        )
        await message.reply(f"✅ Post ID `{msg_id_to_save}` ko successfully promo list mein add kar diya gaya hai!")
    except Exception as e:
        await message.reply(f"❌ Add Error: {str(e)}")


# ----------------- ON / OFF SYSTEM ----------------- #

@app.on_message(filters.command(["apon"]))
async def turn_on_promo(client, message: Message):
    """Turn ON the auto promo system"""
    await apauthdb.update_one({"_id": "config"}, {"$set": {"is_active": True}}, upsert=True)
    await message.reply("✅ **Auto Promo System ab ON kar diya gaya hai!**\nNaye promos interval ke hisaab se send honge.")

@app.on_message(filters.command(["apoff"]))
async def turn_off_promo(client, message: Message):
    """Turn OFF the auto promo system and delete past promos"""
    # 1. Update config to stop posting
    await apauthdb.update_one({"_id": "config"}, {"$set": {"is_active": False}}, upsert=True)
    
    status_msg = await message.reply("⏳ **Auto Promo OFF kar diya gaya hai!**\n🗑️ Ab tak send kiye gaye sabhi promos delete kiye ja rahe hain, kripya pratiksha karein...")
    
    # 2. Fetch all tracked promos and delete them from the channels
    deleted_count = 0
    failed_count = 0
    
    cursor = apauthdb.find({"post_type": "promo_track"})
    async for p in cursor:
        try:
            await app.delete_messages(chat_id=p["channel_id"], message_ids=p["message_id"])
            deleted_count += 1
        except FloodWait as e:
            await asyncio.sleep(e.value + 2)
            try:
                await app.delete_messages(chat_id=p["channel_id"], message_ids=p["message_id"])
                deleted_count += 1
            except:
                failed_count += 1
        except Exception:
            failed_count += 1
            
        # Delete record from DB once removed
        await apauthdb.delete_one({"_id": p["_id"]})
        
    await status_msg.edit_text(f"✅ **Auto Promo System OFF!**\n\n🗑️ **{deleted_count}** promos successfully delete kar diye gaye hain.\n❌ **{failed_count}** errors aaye (kisi channel me bot admin na hone par).")


# ----------------- MAIN CHANNEL SETUP ----------------- #

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
            bot_status = await get_bot_status(channel_id)
        except Exception as e:
            return await message.reply(f"❌ Channel access failed: `{e}`")

        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {
                "main_channel": channel_id,
                "loop_running": True
            }},
            upsert=True
        )

        await message.reply(
            f"✅ Main channel set: `{chat.title}`\n"
            f"🆔 ID: `{channel_id}`\n\n"
            f"📝 Channel me post karo, bot 👍 react karega!"
        )
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

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

        await message.reply("✅ Main channel unauth successfully!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")


# ----------------- PROMO CHANNELS SETUP ----------------- #

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
                status_str = str(member.status).split('.')[-1].lower()
                if status_str in ["administrator", "creator", "owner"]:
                    collected_channels[chat_id]["add"].append(ch_id)
                try:
                    await message.delete()
                except:
                    pass
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

@app.on_message(filters.command(["addpromochnl", "apc"]))
async def add_promo_channel(client, message: Message):
    try:
        chat_id = message.chat.id

        if "-b" in message.text:
            bulk_add_active[chat_id] = True
            collected_channels[chat_id] = {"add": [], "remove": []}
            await message.reply("📥 Bulk Add Start! 1 min ke andar channels se msg forward karein! ⏳")
            await asyncio.sleep(60)

            bulk_add_active[chat_id] = False
            config = await get_config()
            existing = set(config.get("promo_channels", []))

            added = 0
            failed = 0

            for ch_id in collected_channels.get(chat_id, {}).get("add", []):
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

            if chat_id in collected_channels:
                del collected_channels[chat_id]

            await message.reply(
                f"✅ Bulk Done!\n\n"
                f"✅ Added: {added}\n"
                f"❌ Failed: {failed}\n"
                f"📊 Total: {len(existing)}"
            )
            return

        if message.reply_to_message:
            if message.reply_to_message.forward_from_chat:
                channel_id = message.reply_to_message.forward_from_chat.id
            else:
                return await message.reply("❌ Reply karo forwarded msg ko!")
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
                return await message.reply(f"❌ Bot is {member.status}\n\n⚠️ Bot ko us channel mein Admin banao pehle!")

            if member.privileges and not member.privileges.can_post_messages:
                return await message.reply(f"⚠️ Bot admin hai par Post Messages ki permission nahi hai!")
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
            await message.reply(f"ℹ️ Already added in the list!")

    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@app.on_message(filters.command(["rmaddpromochnl", "rmapc"]))
async def remove_promo_channel(client, message: Message):
    try:
        chat_id = message.chat.id

        if "-b" in message.text:
            bulk_remove_active[chat_id] = True
            collected_channels[chat_id] = {"add": [], "remove": []}
            await message.reply("🗑️ Bulk Remove Start! 1 min ke andar channels se msg forward karein! ⏳")
            await asyncio.sleep(60)

            bulk_remove_active[chat_id] = False
            config = await get_config()
            promo_channels = set(config.get("promo_channels", []))
            removed = 0

            for ch_id in collected_channels.get(chat_id, {}).get("remove", []):
                if ch_id in promo_channels:
                    promo_channels.remove(ch_id)
                    removed += 1

            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_channels": list(promo_channels)}},
                upsert=True
            )

            if chat_id in collected_channels:
                del collected_channels[chat_id]

            await message.reply(f"✅ Bulk Done!\n\n🗑️ Removed: {removed}\n📊 Remaining: {len(promo_channels)}")
            return

        if message.reply_to_message:
            if message.reply_to_message.forward_from_chat:
                channel_id = message.reply_to_message.forward_from_chat.id
            else:
                return await message.reply("❌ Reply karo forwarded msg ko!")
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


# ----------------- CONFIG & STATUS ----------------- #

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
            {"$set": {
                "forward_tag": forward_tag,
                "promo_interval": promo_interval
            }},
            upsert=True
        )

        await message.reply(
            f"✅ **Updated**\n\n"
            f"🏷️ Forward Tag: `{'On' if forward_tag else 'Off'}`\n"
            f"⏰ Interval: `{format_time(promo_interval)}`"
        )
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

@app.on_message(filters.command(["apstatus"]))
async def check_status(client, message: Message):
    """Check current bot status and config"""
    try:
        config = await get_config()
        main_channel = config.get("main_channel")
        promo_channels = config.get("promo_channels", [])
        is_active = config.get("is_active", True)

        status_msg = "🔍 **Auto Promo Status**\n\n"
        status_msg += f"🟢 State: `{'ON' if is_active else 'OFF'}`\n\n"

        if main_channel:
            status_msg += f"📢 Main Channel: `{main_channel}`\n"
            bot_status = await get_bot_status(main_channel)
            status_msg += f"🤖 Bot Status: `{bot_status}`\n\n"

            post_count = await apauthdb.count_documents({
                "channel_id": main_channel,
                "post_type": "main_channel",
                "exists": {"$ne": False}
            })
            status_msg += f"📝 Tracked Posts: `{post_count}`\n\n"
        else:
            status_msg += "📢 Main Channel: `Not Set`\n\n"

        status_msg += f"📊 Promo Channels: `{len(promo_channels)}`\n"
        status_msg += f"⏰ Interval: `{format_time(config.get('promo_interval', 18000))}`\n"
        status_msg += f"🏷️ Forward Tag: `{'On' if config.get('forward_tag') else 'Off'}`\n"
        status_msg += f"📍 Current Index: `{config.get('current_post_index', 0)}`"

        await message.reply(status_msg)

    except Exception as e:
        await message.reply(f"❌ Error: {e}")

@app.on_message(filters.command(["forcespromo", "fp", "fpromo"]))
async def force_start_promo(client, message: Message):
    """Force restart promo cycle from beginning + immediate promo"""
    try:
        config = await get_config()

        if not config.get("main_channel"):
            return await message.reply("❌ Main channel set nahi hai! Pehle `/apauth` use karo")
        if not config.get("promo_channels"):
            return await message.reply("❌ Promo channels nahi hain! Pehle `/apc` use karo")
        if not config.get("is_active", True):
            return await message.reply("❌ System abhi OFF hai. Pehle `/apon` karein.")

        post_count = await apauthdb.count_documents({
            "channel_id": config.get("main_channel"),
            "post_type": "main_channel",
            "exists": {"$ne": False}
        })

        if post_count == 0:
            return await message.reply("❌ Koi post track nahi hai! Main channel me post karo ya `/addp` use karo.")

        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {
                "current_post_index": 0,
                "loop_running": True
            }},
            upsert=True
        )

        force_promo_event.set()

        await message.reply(
            "🔄 **Force Promo Triggered!**\n\n"
            "📍 Index reset to 0\n"
            f"📝 Total posts: {post_count}\n"
            "⚡ Immediate promo cycle starting..."
        )
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")


# ----------------- LOOPS & CLEANUP ----------------- #

async def cleanup_deleted_posts():
    """Periodically check and remove deleted posts from tracker to keep DB clean"""
    while True:
        try:
            posts = []
            cursor = apauthdb.find({"post_type": "main_channel", "exists": True})
            async for post in cursor:
                posts.append(post)

            deleted = 0
            for post in posts:
                if not await message_exists(post.get("channel_id"), post.get("message_id")):
                    await apauthdb.update_one({"_id": post["_id"]}, {"$set": {"exists": False}})
                    deleted += 1
                await asyncio.sleep(1)

            # Auto cleanup old promos from tracking DB (7 days)
            result = await apauthdb.delete_many({
                "post_type": "promo_track",
                "posted_at": {"$lt": datetime.utcnow() - timedelta(days=7)}
            })

            await asyncio.sleep(21600)  # Check every 6 hours
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"❌ Cleanup Error: {e}")
            await asyncio.sleep(3600)

async def promo_loop():
    """Main background promo loop"""
    print("🚀 Auto Promo loop started...")
    await apauthdb.update_one({"_id": "config"}, {"$set": {"loop_running": True}}, upsert=True)

    while True:
        try:
            config = await get_config()
            interval = config.get("promo_interval", 18000)

            # Wait for either the set interval OR manual trigger via /forcespromo
            try:
                await asyncio.wait_for(force_promo_event.wait(), timeout=interval)
                force_promo_event.clear()
            except asyncio.TimeoutError:
                pass 

            # Refetch config after sleep
            config = await get_config()
            
            # Agar system OFF hai, toh skip kar do loop ko
            if not config.get("is_active", True):
                await asyncio.sleep(60)
                continue

            main_channel = config.get("main_channel")
            promo_channels = config.get("promo_channels", [])
            current_index = config.get("current_post_index", 0)
            forward_tag = config.get("forward_tag", False)

            if not main_channel or not promo_channels:
                await asyncio.sleep(120)
                continue

            # Fetch valid main channel posts sorted by time
            posts = []
            cursor = apauthdb.find({"post_type": "main_channel", "exists": True}).sort("created_at", 1)
            async for p in cursor:
                posts.append(p)

            if not posts:
                await asyncio.sleep(120)
                continue

            # Ensure index bounds
            if current_index >= len(posts):
                current_index = 0

            post_to_send = posts[current_index]
            msg_id = post_to_send.get("message_id")

            # Check if source post still exists
            if not await message_exists(main_channel, msg_id):
                await apauthdb.update_one({"_id": post_to_send["_id"]}, {"$set": {"exists": False}})
                continue  # Loop again without updating interval

            # Send to all promo channels
            for promo_chat in promo_channels:
                try:
                    sent_msg = None
                    if forward_tag:
                        sent_msg = await app.forward_messages(promo_chat, main_channel, msg_id)
                    else:
                        sent_msg = await app.copy_message(promo_chat, main_channel, msg_id)
                    
                    if sent_msg:
                        # Log it so /apoff can delete it later
                        await apauthdb.insert_one({
                            "post_type": "promo_track",
                            "channel_id": promo_chat,
                            "message_id": sent_msg.id,
                            "posted_at": datetime.utcnow()
                        })
                except FloodWait as e:
                    await asyncio.sleep(e.value + 2)
                except Exception as e:
                    print(f"⚠️ Promo error in chat {promo_chat}: {e}")

            # Next post for the next loop
            await apauthdb.update_one({"_id": "config"}, {"$set": {"current_post_index": current_index + 1}})

        except Exception as e:
            print(f"❌ Promo loop critical error: {e}")
            await asyncio.sleep(60)


# Initialize tasks on module load
asyncio.create_task(cleanup_deleted_posts())
asyncio.create_task(promo_loop())
