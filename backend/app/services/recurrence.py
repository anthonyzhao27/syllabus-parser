"""Deterministic recurrence expansion."""

import logging
from datetime import date, datetime, timedelta
from datetime import time as dt_time
from typing import Generator

from dateutil.relativedelta import relativedelta

from app.models.schemas import (
    ParsedEvent,
    Recurrence,
    RecurrenceFrequency,
    RecurringEvent,
    Weekday,
)

logger = logging.getLogger(__name__)

WEEKDAY_MAP: dict[Weekday, int] = {
    Weekday.MONDAY: 0,
    Weekday.TUESDAY: 1,
    Weekday.WEDNESDAY: 2,
    Weekday.THURSDAY: 3,
    Weekday.FRIDAY: 4,
    Weekday.SATURDAY: 5,
    Weekday.SUNDAY: 6,
}


def _find_first_weekday(start: date, target_weekday: int) -> date:
    """Find the first occurrence of target weekday on or after start date."""
    days_ahead = target_weekday - start.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return start + timedelta(days=days_ahead)


def _generate_weekly_dates(
    start_date: date,
    end_date: date,
    weekday: Weekday,
    interval: int = 1,
    exclusions: set[date] | None = None,
) -> Generator[date, None, None]:
    """Generate all weekly occurrences within the date range."""
    exclusions = exclusions or set()
    target_weekday = WEEKDAY_MAP[weekday]

    if start_date.weekday() != target_weekday:
        raise ValueError(
            f"start_date {start_date} does not match weekday {weekday}"
        )

    current = start_date

    while current <= end_date:
        if current not in exclusions:
            yield current
        current += timedelta(weeks=interval)


def _generate_daily_dates(
    start_date: date,
    end_date: date,
    interval: int = 1,
    exclusions: set[date] | None = None,
) -> Generator[date, None, None]:
    """Generate all daily occurrences within the date range."""
    exclusions = exclusions or set()
    current = start_date

    while current <= end_date:
        if current not in exclusions:
            yield current
        current += timedelta(days=interval)


def _generate_monthly_dates(
    start_date: date,
    end_date: date,
    interval: int = 1,
    exclusions: set[date] | None = None,
) -> Generator[date, None, None]:
    """Generate same-day-of-month monthly occurrences."""
    exclusions = exclusions or set()
    current = start_date

    while current <= end_date:
        if current not in exclusions:
            yield current
        current = current + relativedelta(months=interval)


def expand_recurrence(recurring: RecurringEvent) -> list[ParsedEvent]:
    """Expand a recurring event into individual ParsedEvent instances."""
    rec = recurring.recurrence
    exclusions = set(rec.exclusions) if rec.exclusions else set()

    if rec.frequency == RecurrenceFrequency.DAILY:
        dates = list(_generate_daily_dates(
            rec.start_date, rec.end_date, rec.interval, exclusions
        ))
    elif rec.frequency == RecurrenceFrequency.WEEKLY:
        if rec.weekday is None:
            raise ValueError("Weekly recurrence requires weekday, got None")
        dates = list(_generate_weekly_dates(
            rec.start_date, rec.end_date, rec.weekday, rec.interval, exclusions
        ))
    elif rec.frequency == RecurrenceFrequency.MONTHLY:
        dates = list(_generate_monthly_dates(
            rec.start_date, rec.end_date, rec.interval, exclusions
        ))
    else:
        raise ValueError(f"Unknown frequency: {rec.frequency}")

    events = []
    for i, occurrence_date in enumerate(dates, 1):
        if rec.time:
            dt = datetime.combine(occurrence_date, rec.time)
            time_specified = True
        else:
            dt = datetime.combine(occurrence_date, dt_time(23, 59, 0))
            time_specified = False

        title = f"{recurring.title} {i}" if len(dates) > 1 else recurring.title

        events.append(ParsedEvent(
            title=title,
            due_date=dt,
            course=recurring.course,
            event_type=recurring.event_type,
            description=recurring.description,
            time_specified=time_specified,
            duration_minutes=recurring.duration_minutes,
        ))

    return events


def expand_all_recurrences(
    recurring_events: list[RecurringEvent],
) -> list[ParsedEvent]:
    """Expand all recurring events into individual events."""
    all_events: list[ParsedEvent] = []
    for recurring in recurring_events:
        try:
            expanded = expand_recurrence(recurring)
            all_events.extend(expanded)
        except ValueError as e:
            logger.warning(
                "Skipping invalid recurrence '%s': %s", recurring.title, e
            )
    return all_events
