import os

# Telegram Credentials & Configuration
API_ID = int(os.getenv("TELEGRAM_API_ID", "37601412"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "0bcc06230313618d4ee5dd3bcdcf79dc")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8879179296:AAED-caaVUPWCV3gx6AsR9cg2nx53qGckAs")
SEARCH_BOT_TOKEN = TELEGRAM_BOT_TOKEN
TELEGRAM_CHANNEL = int(os.getenv("TELEGRAM_CHANNEL", "-1004448676495"))
CHANNEL_ID = TELEGRAM_CHANNEL

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Database Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOVIES_DB_FILE = os.path.join(BASE_DIR, "movies.db")
USERS_DB_FILE = os.path.join(BASE_DIR, "data.db")
