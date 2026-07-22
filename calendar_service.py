import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config
from models import EventUpdate, ParsedEvent

_RECURRENCE_RULES = {
    "daily": ["RRULE:FREQ=DAILY"],
    "weekly": ["RRULE:FREQ=WEEKLY"],
}

SCOPES = ["https://www.googleapis.com/auth/calendar"]

_service = None


def _get_credentials() -> Credentials:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    creds = None
    if os.path.exists(config.GOOGLE_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(config.GOOGLE_TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.GOOGLE_CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(config.GOOGLE_TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return creds


def get_service():
    global _service
    if _service is None:
        _service = build("calendar", "v3", credentials=_get_credentials())
    return _service


def _event_body(ev: ParsedEvent) -> dict:
    if ev.all_day:
        end_date = (datetime.strptime(ev.date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        start_body = {"date": ev.date}
        end_body = {"date": end_date}
    else:
        start_dt = f"{ev.date}T{ev.start_time}:00"
        if ev.end_time:
            end_dt = f"{ev.date}T{ev.end_time}:00"
        else:
            start_obj = datetime.strptime(start_dt, "%Y-%m-%dT%H:%M:%S")
            end_obj = start_obj + timedelta(minutes=config.DEFAULT_EVENT_DURATION_MINUTES)
            end_dt = end_obj.strftime("%Y-%m-%dT%H:%M:%S")
        start_body = {"dateTime": start_dt, "timeZone": config.TIMEZONE}
        end_body = {"dateTime": end_dt, "timeZone": config.TIMEZONE}

    body = {
        "summary": ev.title,
        "start": start_body,
        "end": end_body,
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": config.CALENDAR_REMINDER_MINUTES}],
        },
    }
    recurrence = getattr(ev, "recurrence", "")
    if recurrence in _RECURRENCE_RULES:
        body["recurrence"] = _RECURRENCE_RULES[recurrence]
    return body


def create_event(ev: ParsedEvent) -> dict:
    service = get_service()
    body = _event_body(ev)
    return service.events().insert(calendarId=config.GOOGLE_CALENDAR_ID, body=body).execute()


def update_event(update: EventUpdate) -> dict:
    service = get_service()
    body = _event_body(update)
    return (
        service.events()
        .update(calendarId=config.GOOGLE_CALENDAR_ID, eventId=update.event_id, body=body)
        .execute()
    )


def delete_event(event_id: str) -> None:
    service = get_service()
    service.events().delete(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id).execute()


def get_event(event_id: str) -> dict:
    service = get_service()
    return service.events().get(calendarId=config.GOOGLE_CALENDAR_ID, eventId=event_id).execute()


def find_overlaps(ev: ParsedEvent) -> list[dict]:
    if ev.all_day:
        return []
    tz = ZoneInfo(config.TIMEZONE)
    start_dt = datetime.strptime(f"{ev.date} {ev.start_time}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    if ev.end_time:
        end_dt = datetime.strptime(f"{ev.date} {ev.end_time}", "%Y-%m-%d %H:%M").replace(tzinfo=tz)
    else:
        end_dt = start_dt + timedelta(minutes=config.DEFAULT_EVENT_DURATION_MINUTES)

    day_start = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    overlaps = []
    for other in list_events(day_start, day_start + timedelta(days=1)):
        other_start = other["start"].get("dateTime")
        other_end = other["end"].get("dateTime")
        if not other_start or not other_end:
            continue
        other_start_dt = datetime.fromisoformat(other_start)
        other_end_dt = datetime.fromisoformat(other_end)
        if start_dt < other_end_dt and other_start_dt < end_dt:
            overlaps.append(other)
    return overlaps


def list_events(time_min: datetime, time_max: datetime) -> list[dict]:
    service = get_service()
    result = (
        service.events()
        .list(
            calendarId=config.GOOGLE_CALENDAR_ID,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return result.get("items", [])
