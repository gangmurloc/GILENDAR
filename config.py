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

# 자유시간 계산에 쓰이는 하루 활동 시간대 (이 시간 밖은 자유시간으로 치지 않음)
FREE_TIME_START_HOUR = int(os.getenv("FREE_TIME_START_HOUR", "9"))
FREE_TIME_END_HOUR = int(os.getenv("FREE_TIME_END_HOUR", "24"))
FREE_SLOT_MIN_MINUTES = int(os.getenv("FREE_SLOT_MIN_MINUTES", "30"))
CALENDAR_CONTEXT_DAYS = int(os.getenv("CALENDAR_CONTEXT_DAYS", "7"))

MORNING_DIGEST_HOUR = int(os.getenv("MORNING_DIGEST_HOUR", "8"))

DATA_DIR = os.getenv("DATA_DIR", "data")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
GOOGLE_TOKEN_PATH = os.getenv("GOOGLE_TOKEN_PATH", os.path.join(DATA_DIR, "token.json"))
