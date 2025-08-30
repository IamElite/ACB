# DURGESH/__init__.py

import time
import asyncio
from pyrogram import Client, idle
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
from config import *

# Replace logger with print
START_TIME = time.time()
print(f"[{START_TIME:.0f}] - DURGESH - Initializing...")

# Database Connection
db = AsyncIOMotorClient(MONGO_URL).Durgesh
print(f"[{time.time():.0f}] - DURGESH - MongoDB connected.")

# Web Server Setup
routes = web.RouteTableDef()

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response({"status": "bot is running"})

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="DURGESH",
            api_id=API_ID,
            api_hash=API_HASH,
            workers=TG_BOT_WORKERS,
            bot_token=BOT_TOKEN,
        )

    async def start(self, *args, **kwargs):
        await super().start(*args, **kwargs)
        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        print(f"[{time.time():.0f}] - DURGESH - Bot started as {self.name} (@{self.username}).")
        
        # Start Web Server
        app = web.AppRunner(await web_server())
        await app.setup()
        site = web.TCPSite(app, "0.0.0.0", PORT)
        await site.start()
        print(f"[{time.time():.0f}] - DURGESH - 🌐 Web server started on port {PORT}")

    async def stop(self, *args):
        await super().stop()
        print(f"[{time.time():.0f}] - DURGESH - 🛑 Bot stopped.")

    @property
    def mention(self):
        return f"[{self.name}](tg://user?id={self.id})"

app = Bot()
