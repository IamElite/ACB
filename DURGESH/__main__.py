# DURGESH/__main__.py

import config
from DURGESH import app
import logging

# Logger
LOGGER = logging.getLogger("DURGESH")

# Startup message
@app.on_bot_startup
async def bot_startup():
    try:
        owner_id = int(config.OWNER_ID)
        await app.send_message(owner_id, f"{app.mention} **has started! 🚀**")
        LOGGER.info("Startup message sent to owner.")
    except Exception as e:
        LOGGER.warning(f"Failed to send startup message: {e}")

if __name__ == "__main__":
    try:
        app.run()  
    except Exception as e:
        LOGGER.critical(f"Failed to start bot: {e}")
        raise
