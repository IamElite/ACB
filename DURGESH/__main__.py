# __main__.py

import importlib
import asyncio
from pyrogram import idle
import config
from DURGESH import app
from DURGESH.modules import ALL_MODULES

async def boot():
    await app.start()

    # Load all modules
    for module in ALL_MODULES:
        importlib.import_module(f"DURGESH.modules.{module}")
        print(f"Loaded module: {module}")

    # Notify owner
    try:
        owner_id = int(config.OWNER_ID)
        await app.send_message(owner_id, f"{app.mention} **has started! 🚀**")
    except Exception as ex:
        print("Error sending startup message:", ex)

    # Keep the bot running
    await idle()

    # Graceful shutdown
    await app.stop()

if __name__ == "__main__":
    # This is the correct way to run an async main function
    asyncio.run(boot())
