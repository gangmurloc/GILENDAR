import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from telegram.ext import ContextTypes

import calendar_service
import config

_NOTIFIED_PATH = os.path.join(config.DATA_DIR, "notified_events.json")


def _load_notified() -> set:
    if not os.path.exists(_NOTIFIED_PATH):
        return set()
    with open(_NOTIFIED_PATH, "r", encoding="utf-8") as f:
        return set(json.load(f))


def _save_notified(ids: set):
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(_NOTIFIED_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False)


def _popup_minutes(ev: dict) -> int:
    overrides = ev.get("reminders", {}).get("overrides", [])
    for override in overrides:
        if override.get("method") == "popup":
            return override["minutes"]
    return config.TELEGRAM_REMINDER_MINUTES


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    # 이벤트별로 알림 시간이 다를 수 있으므로(예: "1시간 전에 알려줘") 넉넉히 하루치를 미리 본다.
    horizon = now + timedelta(hours=24)
    events = calendar_service.list_events(now, horizon)

    notified = _load_notified()
    changed = False
    for ev in events:
        start_raw = ev["start"].get("dateTime")
        if not start_raw:
            continue  # all-day events have no single reminder instant
        start_dt = datetime.fromisoformat(start_raw)
        remind_at = start_dt - timedelta(minutes=_popup_minutes(ev))
        key = ev["id"]
        if now >= remind_at and key not in notified:
            title = ev.get("summary", "(제목 없음)")
            time_str = start_dt.astimezone(tz).strftime("%H:%M")
            await context.bot.send_message(
                chat_id=config.TELEGRAM_OWNER_ID,
                text=f"⏰ {_popup_minutes(ev)}분 후 일정: {title} ({time_str})",
            )
            notified.add(key)
            changed = True

    if changed:
        _save_notified(notified)
