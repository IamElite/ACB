# DURGESH/__init__.py

import time
import logging
import asyncio
from pyrogram import Client, idle 
from motor.motor_asyncio import AsyncIOMotorClient
from aiohttp import web
from config import * 

# Logger Setup
logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.INFO,
)
LOGGER = logging.getLogger("DURGESH")

# Database Connection
db = AsyncIOMotorClient(config.MONGO_URL).Anonymous
START_TIME = time.time()

# Web Server Setup
routes = web.RouteTableDef()
#PORT = config.PORT

@routes.get("/", allow_head=True)
async def root_route_handler(request):
    return web.json_response({"status": "bot is running"})

async def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    return web_app


class Bot(Client): # <-- Pyrogram ka Client class inherit kiya gaya hai
    def __init__(self):
        super().__init__(
            name="DURGESH",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            workers=TG_BOT_WORKERS,
            bot_token=config.BOT_TOKEN,
        )

    async def start(self, *args, **kwargs):
        await super().start(*args, **kwargs)
        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        LOGGER.info(f"Bot started as {self.name} (@{self.username}). ")
        # Start Web Server
        app = web.AppRunner(await web_server())
        await app.setup()
        site = web.TCPSite(app, "0.0.0.0", PORT)
        await site.start()
        LOGGER.info(f"🌐 Web server started on port {PORT}")

    async def stop(self, *args):
        await super().stop()
        LOGGER.info("🛑 Bot stopped.")

    @property
    def mention(self):
        return f"[{self.name}](tg://user?id={self.id})"

app = Bot()




