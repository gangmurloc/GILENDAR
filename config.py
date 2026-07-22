import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"환경변수 {name}가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return value


TELEGRAM_BOT_TOKEN = _require("TELEGRAM_BOT_TOKEN")
TELEGRAM_OWNER_ID = int(_require("TELEGRAM_OWNER_ID"))

GEMINI_API_KEY = _require("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")

GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Seoul")

CALENDAR_REMINDER_MINUTES = int(os.getenv("CALENDAR_REMINDER_MINUTES", "10"))
TELEGRAM_REMINDER_MINUTES = int(os.getenv("TELEGRAM_REMINDER_MINUTES", "10"))
DEFAULT_EVENT_DURATION_MINUTES = int(os.getenv("DEFAULT_EVENT_DURATION_MINUTES", "60"))

DATA_DIR = os.getenv("DATA_DIR", "data")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", os.path.join(DATA_DIR, "token.json"))
