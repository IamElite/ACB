# DURGESH/__main__.py

import importlib

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
        await app.send_message(owner_id, f"{app.mention} **ʜᴀs sᴛᴀʀᴛᴇᴅ 🥳**")
    except Exception as ex:
        print("Eʀʀᴏʀ sᴇɴᴅɪɴɢ sᴛᴀʀᴛᴜᴘ ᴍᴇssᴀɢᴇ ᴛᴏ ᴏᴡɴᴇʀ:", ex)
    
    await idle()
    await app.stop()

if __name__ == "__main__":
    app.run(boot())

if __name__ == "__main__":
    app.run(boot())

