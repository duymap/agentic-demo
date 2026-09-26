import os

from dotenv import load_dotenv

load_dotenv()

OMLX_BASE_URL = os.getenv("OMLX_BASE_URL", "http://127.0.0.1:8001/v1")
OMLX_API_KEY = os.getenv("OMLX_API_KEY", "local")
MODEL_ID = os.environ["MODEL_ID"]
ENABLE_THINKING = os.getenv("ENABLE_THINKING", "false").lower() == "true"
JWT_SECRET = os.environ["JWT_SECRET"]
DB_PATH = os.getenv("DB_PATH", "./data/demo.db")
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "./data/sessions")
TURN_TIMEOUT_S = int(os.getenv("TURN_TIMEOUT_S", "300"))
