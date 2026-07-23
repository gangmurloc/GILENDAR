from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import calendar_service
import config

WEEKDAY_KR = ["월", "화", "수", "목", "금", "토", "일"]


def _day_window(day, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time(config.FREE_TIME_START_HOUR, 0), tzinfo=tz)
    if config.FREE_TIME_END_HOUR >= 24:
        end = datetime.combine(day + timedelta(days=1), time(0, 0), tzinfo=tz)
    else:
        end = datetime.combine(day, time(config.FREE_TIME_END_HOUR, 0), tzinfo=tz)
    return start, end


def free_slots_for_range(now: datetime, days: int) -> list[tuple[datetime.date, list[tuple[datetime, datetime]]]]:
    tz = now.tzinfo
    results = []
    for offset in range(days):
        day = (now + timedelta(days=offset)).date()
        day_start, day_end = _day_window(day, tz)
        window_start = max(day_start, now) if offset == 0 else day_start
        if window_start >= day_end:
            results.append((day, []))
            continue

        events = calendar_service.list_events(day_start, day_end)
        busy = []
        for ev in events:
            s = ev["start"].get("dateTime")
            e = ev["end"].get("dateTime")
            if not s or not e:
                continue  # all-day events don't block a specific time slot
            busy.append((datetime.fromisoformat(s).astimezone(tz), datetime.fromisoformat(e).astimezone(tz)))
        busy.sort()

        cursor = window_start
        free = []
        for s, e in busy:
            if s > cursor:
                free.append((cursor, min(s, day_end)))
            cursor = max(cursor, e)
        if cursor < day_end:
            free.append((cursor, day_end))

        free = [(s, e) for s, e in free if (e - s) >= timedelta(minutes=config.FREE_SLOT_MIN_MINUTES)]
        results.append((day, free))
    return results


def format_free_slots(slots: list[tuple[datetime.date, list[tuple[datetime, datetime]]]]) -> str:
    lines = []
    for day, free in slots:
        weekday = WEEKDAY_KR[day.weekday()]
        if not free:
            lines.append(f"{day.month}/{day.day}({weekday}): 자유시간 없음")
            continue
        parts = [f"{s.strftime('%H:%M')}~{e.strftime('%H:%M')}" for s, e in free]
        lines.append(f"{day.month}/{day.day}({weekday}): " + ", ".join(parts))
    return "\n".join(lines)


def build_calendar_context(now: datetime) -> str:
    """Gemini에게 넘길, 현재 등록된 일정과 자유시간 정보를 요약한 텍스트."""
    tz = now.tzinfo
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    events = calendar_service.list_events(day_start, day_start + timedelta(days=config.CALENDAR_CONTEXT_DAYS))

    event_lines = []
    for ev in events:
        title = ev.get("summary", "(제목 없음)")
        event_id = ev["id"]
        date_time = ev["start"].get("dateTime")
        if date_time:
            dt = datetime.fromisoformat(date_time).astimezone(tz)
            weekday = WEEKDAY_KR[dt.weekday()]
            end_raw = ev.get("end", {}).get("dateTime")
            if end_raw:
                end_dt = datetime.fromisoformat(end_raw).astimezone(tz)
                time_part = f"{dt.strftime('%H:%M')}~{end_dt.strftime('%H:%M')}"
            else:
                time_part = dt.strftime("%H:%M")
            event_lines.append(f"- [id:{event_id}] {dt.month}/{dt.day}({weekday}) {time_part} {title}")
        else:
            d = datetime.strptime(ev["start"]["date"], "%Y-%m-%d")
            weekday = WEEKDAY_KR[d.weekday()]
            event_lines.append(f"- [id:{event_id}] {d.month}/{d.day}({weekday}) 종일 {title}")
    events_text = "\n".join(event_lines) if event_lines else "(등록된 일정 없음)"

    slots = free_slots_for_range(now, config.CALENDAR_CONTEXT_DAYS)
    free_text = format_free_slots(slots)

    return (
        f"[등록된 일정 (앞으로 {config.CALENDAR_CONTEXT_DAYS}일)]\n{events_text}\n\n"
        f"[자유시간, {config.FREE_TIME_START_HOUR}시~{config.FREE_TIME_END_HOUR}시 기준]\n{free_text}"
    )
