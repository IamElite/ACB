from . import chatsdb

async def is_chatbot_enabled(chat_id: int) -> bool:
    """Checks if chatbot is enabled for a group."""
    chat = await chatsdb.find_one({"chat_id": chat_id})
    return chat is None

async def enable_chatbot(chat_id: int):
    """Enables chatbot for a group."""
    await chatsdb.delete_one({"chat_id": chat_id})

async def disable_chatbot(chat_id: int):
    """Disables chatbot for a group."""
    if not await chatsdb.find_one({"chat_id": chat_id}):
        await chatsdb.insert_one({"chat_id": chat_id})

async def get_enabled_chats() -> list:
    """Returns a list of chat IDs where chatbot is enabled."""
    chats = await chatsdb.find({}, {"chat_id": 1, "_id": 0}).to_list(length=None)
    return [chat["chat_id"] for chat in chats]
