from pydantic import BaseModel


class ParsedEvent(BaseModel):
    title: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM, 24h
    end_time: str  # HH:MM, empty string if not specified
    all_day: bool
    recurrence: str  # "", "daily", or "weekly"
    reminder_minutes: str  # minutes before start as a string (e.g. "60"), "" to use the default


class EventUpdate(BaseModel):
    event_id: str  # must match an id from the given calendar context
    title: str
    date: str
    start_time: str
    end_time: str
    all_day: bool


class AssistantResponse(BaseModel):
    action: str  # "add", "update", "delete", or "question"
    events: list[ParsedEvent]  # filled when action == "add"
    updates: list[EventUpdate]  # filled when action == "update"
    delete_ids: list[str]  # filled when action == "delete", ids from the calendar context
    reply: str  # filled when action == "question"
