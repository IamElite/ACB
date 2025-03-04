from motor.motor_asyncio import AsyncIOMotorClient
import config

# Database connection
DURGESH = AsyncIOMotorClient(config.MONGO_URL)
db = DURGESH["DURGSH"]  # Database
usersdb = db["users"]    # Users Collection
chatsdb = db["chats"]    # Chats Collection

# Import functions for use in other parts of the application
from .chats import *
from .admin import *
from .fsub import *
from .durga import *
from .chatbot import *
from .extra import *
