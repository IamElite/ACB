import time
import logging
import asyncio
from pyrogram import Client, idle
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

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="DURGESH",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.BOT_TOKEN,
        )

    async def start(self, *args, **kwargs):
        """Starts the bot and logs details"""
        await super().start()
        self.id = self.me.id
        self.name = self.me.first_name
        self.username = self.me.username
        LOGGER.info(f"Bot started as {self.name} (@{self.username}). ")

    async def stop(self):
        """Stops the bot gracefully"""
        await super().stop()
        LOGGER.info("Bot stopped.")

    @property
    def mention(self):
        return f"[{self.name}](tg://user?id={self.id})"

app = Bot()

if __name__ == "__main__":
    async def main():
        await app.start()
        try:
            owner_id = int(config.OWNER_ID)
            LOGGER.info(f"Sending startup message to owner with ID: {owner_id}")
            await app.send_message(owner_id, f"{app.mention} has started")
        except Exception as ex:
            LOGGER.exception("Error sending startup message")
        await idle()
        await app.stop()

    asyncio.run(main())
