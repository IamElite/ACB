# auto_promo.py

import asyncio
from datetime import datetime, timedelta
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ChatAdminRequired, UserNotParticipant
from DURGESH import app
from DURGESH.database import db

apauthdb = db.apauth_channels

# Background task reference
promo_task = None

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
        return 18000  # default 5h
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
            "promo_interval": 18000,  # 5h default
            "current_post_index": 0,
            "last_promo_time": None
        }
        await apauthdb.insert_one(config)
    return config

# Global handler to collect forwarded channels in bulk mode
@app.on_message(filters.forwarded)
async def bulk_collector(client, message: Message):
    """Collect forwarded channels when bulk mode is active"""
    chat_id = message.chat.id
    
    # Check if bulk add mode is active for this chat
    if chat_id in bulk_add_active and bulk_add_active[chat_id]:
        if message.forward_from_chat:
            ch_id = message.forward_from_chat.id
            
            if chat_id not in collected_channels:
                collected_channels[chat_id] = {"add": [], "remove": []}
            
            try:
                # Check if bot is admin
                member = await client.get_chat_member(ch_id, "me")
                if member.status in ["administrator", "creator"]:
                    collected_channels[chat_id]["add"].append(ch_id)
                    # Delete the forwarded message
                    try:
                        await message.delete()
                    except:
                        pass
                else:
                    collected_channels[chat_id]["add"].append(None)  # Mark as failed
            except:
                collected_channels[chat_id]["add"].append(None)  # Mark as failed
    
    # Check if bulk remove mode is active for this chat
    elif chat_id in bulk_remove_active and bulk_remove_active[chat_id]:
        if message.forward_from_chat:
            ch_id = message.forward_from_chat.id
            
            if chat_id not in collected_channels:
                collected_channels[chat_id] = {"add": [], "remove": []}
            
            collected_channels[chat_id]["remove"].append(ch_id)
            
            # Delete the forwarded message
            try:
                await message.delete()
            except:
                pass

# Auth main channel
@app.on_message(filters.command(["apauth"]))
async def auth_main_channel(client, message: Message):
    try:
        # Get channel id from reply or args
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
        
        # Update config
        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {"main_channel": channel_id}},
            upsert=True
        )
        
        await message.reply(f"✅ Main channel auth ho gaya: `{channel_id}`\n\n🚀 Promo loop active hai, jab posts honge tab promote karunga!")
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Unauth main channel
@app.on_message(filters.command(["apunauth"]))
async def unauth_main_channel(client, message: Message):
    try:
        await apauthdb.update_one(
            {"_id": "config"},
            {"$set": {"main_channel": None, "current_post_index": 0}},
            upsert=True
        )
        
        await message.reply("✅ Main channel unauth ho gaya! Loop ab sleep mode me jayega.")
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# Add promo channel
@app.on_message(filters.command(["addpromochnl", "apc"]))
async def add_promo_channel(client, message: Message):
    try:
        chat_id = message.chat.id
        
        # Check for bulk mode
        if "-b" in message.text:
            # Activate bulk mode
            bulk_add_active[chat_id] = True
            collected_channels[chat_id] = {"add": [], "remove": []}
            
            await message.reply(
                "📥 **Bulk Add Mode Active!**\n\n"
                "Abhi 1 minute hai! Jitne bhi channels add karne hain, sab forward karo yahan!\n"
                "Jo channels mein bot admin hoga, vo add ho jayenge. ⏳"
            )
            
            # Wait for 1 minute
            await asyncio.sleep(60)
            
            # Deactivate bulk mode
            bulk_add_active[chat_id] = False
            
            # Process collected channels
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
            
            # Update DB
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_channels": list(existing)}},
                upsert=True
            )
            
            # Clean up
            del collected_channels[chat_id]
            
            await message.reply(
                f"✅ **Bulk Add Complete!**\n\n"
                f"✅ Added: {added}\n"
                f"❌ Failed: {failed}\n"
                f"📊 Total promo channels: {len(existing)}"
            )
            return
        
        # Normal add mode
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
        
        # Check for bulk mode
        if "-b" in message.text:
            # Activate bulk remove mode
            bulk_remove_active[chat_id] = True
            collected_channels[chat_id] = {"add": [], "remove": []}
            
            await message.reply(
                "🗑️ **Bulk Remove Mode Active!**\n\n"
                "Abhi 1 minute hai! Jo channels remove karne hain vo forward karo!"
            )
            
            # Wait for 1 minute
            await asyncio.sleep(60)
            
            # Deactivate bulk mode
            bulk_remove_active[chat_id] = False
            
            # Process collected channels
            config = await get_config()
            promo_channels = set(config.get("promo_channels", []))
            removed = 0
            
            for ch_id in collected_channels[chat_id]["remove"]:
                if ch_id in promo_channels:
                    promo_channels.remove(ch_id)
                    removed += 1
            
            # Update DB
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {"promo_channels": list(promo_channels)}},
                upsert=True
            )
            
            # Clean up
            del collected_channels[chat_id]
            
            await message.reply(
                f"✅ **Bulk Remove Complete!**\n\n"
                f"🗑️ Removed: {removed}\n"
                f"📊 Remaining channels: {len(promo_channels)}"
            )
            return
        
        # Normal remove
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
        
        # Parse -f flag
        if "-f" in args:
            idx = args.index("-f")
            if len(args) > idx + 1:
                val = args[idx + 1].lower()
                forward_tag = val == "on"
        
        # Parse -t flag
        if "-t" in args:
            idx = args.index("-t")
            if len(args) > idx + 1:
                promo_interval = parse_time(args[idx + 1])
        
        # Update DB
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

# Background promo loop
async def promo_loop():
    """Main background loop for auto promotion - runs continuously"""
    print("🚀 Promo loop started!")
    
    while True:
        try:
            config = await get_config()
            
            main_channel = config.get("main_channel")
            promo_channels = config.get("promo_channels", [])
            forward_tag = config.get("forward_tag", False)
            promo_interval = config.get("promo_interval", 18000)
            current_index = config.get("current_post_index", 0)
            
            # Check if main channel is set
            if not main_channel:
                print("⏸️ Main channel nahi hai, 2 min sleep kar raha hu...")
                await asyncio.sleep(120)
                continue
            
            # Check if promo channels exist
            if not promo_channels:
                print("⏸️ Promo channels nahi hai, 2 min sleep kar raha hu...")
                await asyncio.sleep(120)
                continue
            
            # Get posts from main channel
            print(f"🔍 Checking posts in main channel: {main_channel}")
            posts = []
            try:
                async for msg in app.get_chat_history(main_channel, limit=50):
                    if msg.text or msg.media:
                        posts.append(msg)
            except Exception as e:
                print(f"❌ Main channel access error: {e}")
                await asyncio.sleep(300)
                continue
            
            # If no posts found, wait and recheck
            if not posts:
                print("😴 Main channel me koi post nahi hai, 5 min sleep kar raha hu...")
                await asyncio.sleep(300)
                continue
            
            print(f"✅ {len(posts)} posts milein! Promotion shuru kar raha hu...")
            
            # Rotate to current post
            if current_index >= len(posts):
                current_index = 0
            
            current_post = posts[current_index]
            
            # Promote to all channels
            success_count = 0
            fail_count = 0
            
            for channel_id in promo_channels:
                try:
                    # Delete old promo if exists
                    last_msg_data = await apauthdb.find_one({"channel_id": channel_id})
                    if last_msg_data and last_msg_data.get("last_msg_id"):
                        try:
                            await app.delete_messages(channel_id, last_msg_data["last_msg_id"])
                        except:
                            pass
                    
                    # Send new promo
                    if forward_tag:
                        sent = await current_post.forward(channel_id)
                    else:
                        sent = await current_post.copy(channel_id)
                    
                    # Store new message id
                    await apauthdb.update_one(
                        {"channel_id": channel_id},
                        {"$set": {
                            "last_msg_id": sent.id,
                            "posted_at": datetime.now()
                        }},
                        upsert=True
                    )
                    
                    success_count += 1
                    await asyncio.sleep(2)
                    
                except FloodWait as e:
                    print(f"⚠️ FloodWait {e.value}s for channel {channel_id}")
                    await asyncio.sleep(e.value)
                    fail_count += 1
                except Exception as e:
                    print(f"❌ Failed to promote in {channel_id}: {e}")
                    fail_count += 1
            
            print(f"✅ Promotion complete! Success: {success_count}, Failed: {fail_count}")
            
            # Update index for next cycle
            current_index = (current_index + 1) % len(posts)
            await apauthdb.update_one(
                {"_id": "config"},
                {"$set": {
                    "current_post_index": current_index,
                    "last_promo_time": datetime.now()
                }},
                upsert=True
            )
            
            print(f"⏰ Next promo in {format_time(promo_interval)}...")
            
            # Wait for next cycle
            await asyncio.sleep(promo_interval)
            
        except asyncio.CancelledError:
            print("🛑 Promo loop cancelled!")
            break
        except Exception as e:
            print(f"❌ Promo loop error: {e}")
            await asyncio.sleep(120)

# Startup handler
async def start_promo_on_boot():
    """Start promo loop when bot boots up"""
    global promo_task
    
    await asyncio.sleep(5)
    
    print("🔥 Bot started! Promo loop ko background mein start kar raha hu...")
    promo_task = asyncio.create_task(promo_loop())
    print("✅ Promo loop background task created!")

# Create startup task
asyncio.create_task(start_promo_on_boot())
