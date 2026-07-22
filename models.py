from pydantic import BaseModel


class ParsedEvent(BaseModel):
    title: str
    date: str  # YYYY-MM-DD
    start_time: str  # HH:MM, 24h
    end_time: str  # HH:MM, empty string if not specified
    all_day: bool


class ParsedEventList(BaseModel):
    events: list[ParsedEvent]
