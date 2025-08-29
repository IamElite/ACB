# DURGESH/__init__.py

import time
import logging
import asyncio
from pyrogram import Client, idle # <-- Ye Pyrogram se import ho raha hai
from motor.motor_asyncio import AsyncIOMotorClient
import config

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

class Bot(Client): # <-- Pyrogram ka Client class inherit ho raha hai
    def __init__(self):
        super().__init__(
            name="DURGESH",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
        )

    async def start(self, *args, **kwargs):
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        LOGGER.info(f"Bot started as {self.name} (@{self.username}). ")

    async def stop(self):
        await super().stop()
        LOGGER.info("Bot stopped.")

    @property
    def mention(self):
        return f"[{self.name}](tg://user?id={self.id})"

app = Bot() # <-- Bot ka instance ban raha hai
