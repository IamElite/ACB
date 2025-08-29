import importlib
import asyncio
from pyrogram import idle
import config
from DURGESH import app
from DURGESH.modules import ALL_MODULES


async def boot():
    await app.start()

    for module in ALL_MODULES:
        importlib.import_module(f"DURGESH.modules.{module}")

    try:
        owner_id = int(config.OWNER_ID)
        await app.send_message(owner_id, f"{app.mention} **has started! 🎉**")
    except Exception as ex:
        print("Error sending startup message to owner:", ex)

    await idle()  # Keeps the bot running
    await app.stop()


if __name__ == "__main__":
    asyncio.run(boot())  # ✅ Proper way when .run() doesn't support coroutines
