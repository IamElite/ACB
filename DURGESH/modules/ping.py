from datetime import datetime
import time
import os
import shutil
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import ParseMode

from DURGESH import app

# Ensure bot start time is set
if not hasattr(app, "start_time"):
    app.start_time = time.time()

def get_readable_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"

def get_cpu_usage():
    try:
        # os.getloadavg() returns (1, 5, 15) minutes load average
        load1 = os.getloadavg()[0]  # 1-minute average
        cpu_count = os.cpu_count() or 1
        # Rough estimation of CPU usage percentage:
        cpu_percent = (load1 / cpu_count) * 100
        return round(cpu_percent, 2)
    except Exception as e:
        return "N/A"

def get_memory_usage():
    try:
        meminfo = {}
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split(':')
                if len(parts) >= 2:
                    key = parts[0]
                    value = parts[1].strip().split()[0]
                    meminfo[key] = int(value)
        total = meminfo.get('MemTotal', 0)
        free = meminfo.get('MemFree', 0)
        buffers = meminfo.get('Buffers', 0)
        cached = meminfo.get('Cached', 0)
        used = total - (free + buffers + cached)
        mem_percent = (used / total) * 100 if total else 0
        return round(mem_percent, 2)
    except Exception as e:
        return "N/A"

def get_disk_usage():
    try:
        du = shutil.disk_usage('/')
        disk_percent = (du.used / du.total) * 100
        return round(disk_percent, 2)
    except Exception as e:
        return "N/A"

async def bot_sys_stats():
    bot_uptime = time.time() - app.start_time
    cpu = get_cpu_usage()
    mem = get_memory_usage()
    disk = get_disk_usage()

    UP = get_readable_time(bot_uptime)
    CPU = f"{cpu}%" if isinstance(cpu, (int, float)) else cpu
    RAM = f"{mem}%" if isinstance(mem, (int, float)) else mem
    DISK = f"{disk}%" if isinstance(disk, (int, float)) else disk
    return UP, CPU, RAM, DISK

@app.on_message(filters.command("p"))
async def ping(client, message):
    start = datetime.now()
    UP, CPU, RAM, DISK = await bot_sys_stats()
    
    temp_msg = await message.reply_text("⌛ System stats check kar rahe hain...")
    
    ms = round((datetime.now() - start).total_seconds() * 1000, 2)
    
    text = (
        f"🌟 **{app.me.first_name} Bot Status** 🌟\n\n"
        f"🕒 **Ping:** `{ms} ms`\n"
        f"💻 **CPU Usage:** `{CPU}`\n"
        f"🧠 **RAM Usage:** `{RAM}`\n"
        f"🗄️ **Disk Usage:** `{DISK}`\n"
        f"⏱️ **Uptime:** `{UP}`\n\n"
        f"🚀 Bot full speed pe kaam kar raha hai!\n"
        f"Enjoy and keep exploring!"
    )
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="➕ Add Me", url=f"https://t.me/{app.username}?startgroup"),
            InlineKeyboardButton(text="🔄 Update", url="https://t.me/net_pro_max"),
        ]
    ])
    
    await temp_msg.edit_text(
        text=text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
