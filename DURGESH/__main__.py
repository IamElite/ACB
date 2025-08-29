import importlib
import asyncio
from pyrogram import idle
import config
from DURGESH import app
from DURGESH.modules import ALL_MODULES

import signal

async def boot():
    await app.start()

    for module in ALL_MODULES:
        importlib.import_module(f"DURGESH.modules.{module}")

    try:
        owner_id = int(config.OWNER_ID)
        await app.send_message(owner_id, f"{app.mention} **started! 🚀**")
    except Exception as ex:
        print("Startup message error:", ex)

    # Graceful shutdown on interrupt
    try:
        await idle()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.stop()
