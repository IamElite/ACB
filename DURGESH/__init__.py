# DURGESH/__init__.py

import time
import logging
from kurigram import Client
from motor.motor_asyncio import AsyncIOMotorClient
import config

# Logger Setup
logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s - %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    level=logging.INFO,
)
LOGGER = logging.getLogger("DURGESH")

# Database
db = AsyncIOMotorClient(config.MONGO_URL).Durgesh
START_TIME = time.time()

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="DURGESH",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
            in_memory=True,
            plugins=dict(root="DURGESH/modules")  # Auto-load modules
        )

    async def start(self, *args, **kwargs):
        await super().start(*args, **kwargs)
        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        LOGGER.info(f"Bot started as {self.name} (@{self.username})")

    async def stop(self):
        await super().stop()
        LOGGER.info("Bot stopped.")

    @property
    def mention(self):
        return f"[{self.name}](tg://user?id={self.id})"

# Create app instance
app = Bot()

