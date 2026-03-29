"""OpenAI structured extraction for syllabus parsing."""

import json
import logging
import re

from openai import AsyncOpenAI

from app.config import settings
from app.models.schemas import EventType, ParsedEvent
from app.utils.prompts import EXTRACTION_PROMPT

logger = logging.getLogger(__name__)

DURATION_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?|m|h)\s*$",
    re.IGNORECASE,
)

DEFAULT_DURATIONS: dict[EventType, int] = {
    EventType.EXAM: 120,
    EventType.QUIZ: 30,
    EventType.PRESENTATION: 30,
}

DEFAULT_TIMED_DURATION = 30

DEADLINE_LIKE_TYPES: set[str] = {
    "assignment",
    "project",
    "milestone",
    "deadline",
    "lab",
    "discussion",
    "other",
}


def _parse_duration(value: int | float | str | None) -> int | None:
    if value is None:
        return None

    if isinstance(value, int):
        return value if value > 0 else None

    if isinstance(value, (str, float)):
        try:
            as_int = int(float(value))
            return as_int if as_int > 0 else None
        except (ValueError, TypeError):
            pass

    if isinstance(value, str):
        match = DURATION_PATTERN.match(value.strip())
        if match:
            amount = float(match.group(1))
            unit = match.group(2).lower()

            if unit.startswith("h"):
                minutes = int(amount * 60)
            else:
                minutes = int(amount)

            return minutes if minutes > 0 else None

    return None


def _apply_smart_defaults(event: ParsedEvent) -> ParsedEvent:
    if event.duration_minutes is not None and event.duration_minutes > 0:
        return event

    if not event.time_specified:
        return event

    event_time = event.due_date.time()
    is_2359 = event_time.hour == 23 and event_time.minute == 59
    is_deadline_like = str(event.event_type) in DEADLINE_LIKE_TYPES

    if is_2359 and is_deadline_like:
        adjusted_date = event.due_date.replace(hour=23, minute=30, second=0)
        return ParsedEvent(
            title=event.title,
            due_date=adjusted_date,
            course=event.course,
            event_type=event.event_type,
            description=event.description,
            time_specified=event.time_specified,
            duration_minutes=DEFAULT_TIMED_DURATION,
        )

    duration = DEFAULT_DURATIONS.get(event.event_type, DEFAULT_TIMED_DURATION)

    return ParsedEvent(
        title=event.title,
        due_date=event.due_date,
        course=event.course,
        event_type=event.event_type,
        description=event.description,
        time_specified=event.time_specified,
        duration_minutes=duration,
    )


def _apply_all_smart_defaults(events: list[ParsedEvent]) -> list[ParsedEvent]:
    return [_apply_smart_defaults(e) for e in events]


EVENT_TYPE_SYNONYMS: dict[str, EventType] = {
    "midterm": EventType.EXAM,
    "final": EventType.EXAM,
    "test": EventType.EXAM,
    "homework": EventType.ASSIGNMENT,
    "problem_set": EventType.ASSIGNMENT,
    "hw": EventType.ASSIGNMENT,
    "checkpoint": EventType.MILESTONE,
    "due": EventType.DEADLINE,
    "submission": EventType.DEADLINE,
}


def normalize_event_type(raw: str) -> EventType:
    """Normalize LLM output to canonical EventType."""
    if not raw:
        return EventType.OTHER

    lower = raw.lower().strip()

    try:
        return EventType(lower)
    except ValueError:
        pass

    if lower in EVENT_TYPE_SYNONYMS:
        return EVENT_TYPE_SYNONYMS[lower]

    return EventType.OTHER


def _normalize_event_payload(item: dict) -> dict:
    """Normalize raw LLM event payload before Pydantic validation."""
    normalized = dict(item)
    normalized["event_type"] = normalize_event_type(normalized.get("event_type", ""))
    normalized.setdefault("time_specified", True)
    raw_duration = normalized.get("duration_minutes")
    normalized["duration_minutes"] = _parse_duration(raw_duration)
    return normalized


async def extract_events(text: str) -> list[ParsedEvent]:
    """Send syllabus text to OpenAI and return structured events."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": EXTRACTION_PROMPT},
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    raw = response.choices[0].message.content or ""
    events = _parse_events(raw)
    events = _apply_all_smart_defaults(events)
    return events


def _parse_events(raw: str) -> list[ParsedEvent]:
    """Parse raw JSON string from LLM into validated ParsedEvent list."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON, attempting fence strip")
        stripped = (
            raw.strip()
            .removeprefix("```json")
            .removeprefix("```")
            .removesuffix("```")
            .strip()
        )
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            raise ValueError(f"Could not parse LLM response as JSON: {raw[:200]}")

    if isinstance(data, dict):
        if not data:
            # Empty object {} means no events found
            return []
        for v in data.values():
            if isinstance(v, list):
                data = v
                break
        else:
            raise ValueError(
                f"LLM returned a JSON object with no array field: {raw[:200]}"
            )

    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data).__name__}: {raw[:200]}")

    events: list[ParsedEvent] = []
    for item in data:
        try:
            normalized = _normalize_event_payload(item)
            events.append(ParsedEvent(**normalized))
        except Exception as e:
            logger.warning("Skipping malformed event %r: %s", item, e)
            continue

    return events
