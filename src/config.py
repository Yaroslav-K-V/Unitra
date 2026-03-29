import os
from dotenv import load_dotenv

load_dotenv()

FLASK_PORT       = int(os.getenv("PORT", "5000"))
AI_MODEL         = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
AI_TEMPERATURE   = float(os.getenv("AI_TEMPERATURE", "0.2"))
AI_MAX_CONTEXT   = int(os.getenv("AI_MAX_CONTEXT", "8000"))
PYTEST_TIMEOUT   = int(os.getenv("PYTEST_TIMEOUT", "30"))
MAX_RECENT       = int(os.getenv("MAX_RECENT", "8"))
WINDOW_WIDTH     = int(os.getenv("WINDOW_WIDTH", "1000"))
WINDOW_HEIGHT    = int(os.getenv("WINDOW_HEIGHT", "700"))
