# DURGESH/__main__.py

import asyncio
import logging
from DURGESH import app, db, LOGGER

# Load config
import config


async def main():
    # Start the bot
    await app.start()
    LOGGER.info("Bot started.")

    # Send startup message to owner
    try:
        owner_id = int(config.OWNER_ID)
        await app.send_message(owner_id, f"{app.mention} **has started! 🚀**")
        LOGGER.info("Startup message sent to owner.")
    except ValueError:
        LOGGER.error("OWNER_ID is not a valid integer.")
    except Exception as e:
        LOGGER.warning(f"Failed to send startup message to owner: {e}")

    # Keep the bot running
    LOGGER.info("Bot is now fully operational.")
    await asyncio.Event().wait()  # Keeps the bot running forever


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        LOGGER.info("Received interrupt. Shutting down...")
    except Exception as e:
        LOGGER.critical(f"Failed to start bot: {e}")
        raise
    finally:
        asyncio.get_event_loop().run_until_complete(app.stop())
