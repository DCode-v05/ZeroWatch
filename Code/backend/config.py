import os
from pathlib import Path
from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_db_path = Path(os.path.expanduser("~")) / "zerowatch.db"
DATABASE_URL = f"sqlite:///{_db_path.as_posix()}"
