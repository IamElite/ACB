import importlib

from pyrogram import idle

from DURGESH import app
from DURGESH.modules import ALL_MODULES

async def boot():
    await app.start()

    for module in ALL_MODULES:
        importlib.import_module(f"DURGESH.modules.{module}")

    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(boot())
