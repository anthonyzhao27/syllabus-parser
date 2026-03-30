"""Pydantic request/response models."""

from datetime import date, datetime
from datetime import time as dt_time
from enum import StrEnum

from pydantic import BaseModel, Field


class EventType(StrEnum):
    ASSIGNMENT = "assignment"
    EXAM = "exam"
    QUIZ = "quiz"
    PROJECT = "project"
    LAB = "lab"
    PRESENTATION = "presentation"
    MILESTONE = "milestone"
    DEADLINE = "deadline"
    DISCUSSION = "discussion"
    OTHER = "other"


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Weekday(StrEnum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class Recurrence(BaseModel):
    """Recurrence specification extracted from syllabus.

    Contract:
    - start_date is the first ACTUAL occurrence, not merely the start of a range
    - for weekly recurrences, start_date must already fall on weekday
    - biweekly schedules are represented as frequency=WEEKLY with interval=2

    Note: Monthly weekday patterns such as "first Friday", "second Tuesday", or
    "last Friday" are not supported in this version. Only same-day-of-month
    monthly recurrence is supported.
    """

    frequency: RecurrenceFrequency
    interval: int = Field(default=1, ge=1)
    weekday: Weekday | None = None
    start_date: date
    end_date: date
    time: dt_time | None = None
    exclusions: list[date] = Field(default_factory=list)


class RecurringEvent(BaseModel):
    """A recurring event as extracted by the LLM (before expansion)."""

    title: str
    course: str = ""
    event_type: EventType = EventType.OTHER
    description: str = ""
    recurrence: Recurrence
    duration_minutes: int | None = None


class ParsedEvent(BaseModel):
    title: str
    due_date: datetime
    course: str = ""
    event_type: EventType = EventType.OTHER
    description: str = ""
    time_specified: bool = True
    duration_minutes: int | None = None


class LLMExtractionResult(BaseModel):
    """Raw extraction result from LLM before processing."""

    events: list[ParsedEvent] = Field(default_factory=list)
    recurring_events: list[RecurringEvent] = Field(default_factory=list)


class ParseResponse(BaseModel):
    events: list[ParsedEvent]


class ExportRequest(BaseModel):
    events: list[ParsedEvent]
    format: str = "ics"
    google_token: str | None = None


class ReminderRequest(BaseModel):
    events: list[ParsedEvent]
    phone_number: str


class IcsExportRequest(BaseModel):
    events: list[ParsedEvent]
    filename: str = "syllabus.ics"
    timezone: str


class OutlookExportRequest(BaseModel):
    events: list[ParsedEvent]
    timezone: str


class GoogleExportRequest(BaseModel):
    events: list[ParsedEvent]
    access_token: str | None = None
    calendar_id: str = "primary"
    timezone: str = "UTC"


class GoogleExportResponse(BaseModel):
    created_count: int
    created: list[dict]
    errors: list[dict]
    calendar_name: str
