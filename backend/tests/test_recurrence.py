"""Tests for recurrence expansion."""

from datetime import date
from datetime import time as dt_time

import pytest

from app.models.schemas import (
    EventType,
    Recurrence,
    RecurrenceFrequency,
    RecurringEvent,
    Weekday,
)
from app.services.recurrence import (
    _find_first_weekday,
    _generate_daily_dates,
    _generate_monthly_dates,
    _generate_weekly_dates,
    expand_all_recurrences,
    expand_recurrence,
)


class TestFindFirstWeekday:
    def test_same_day(self):
        result = _find_first_weekday(date(2025, 1, 10), 4)
        assert result == date(2025, 1, 10)

    def test_next_friday(self):
        result = _find_first_weekday(date(2025, 1, 6), 4)
        assert result == date(2025, 1, 10)

    def test_wraps_to_next_week(self):
        result = _find_first_weekday(date(2025, 1, 11), 4)
        assert result == date(2025, 1, 17)


class TestGenerateWeeklyDates:
    def test_fridays_in_january(self):
        dates = list(_generate_weekly_dates(
            start_date=date(2025, 1, 3),
            end_date=date(2025, 1, 31),
            weekday=Weekday.FRIDAY,
        ))
        assert dates == [
            date(2025, 1, 3),
            date(2025, 1, 10),
            date(2025, 1, 17),
            date(2025, 1, 24),
            date(2025, 1, 31),
        ]

    def test_biweekly(self):
        dates = list(_generate_weekly_dates(
            start_date=date(2025, 1, 3),
            end_date=date(2025, 2, 28),
            weekday=Weekday.FRIDAY,
            interval=2,
        ))
        assert dates == [
            date(2025, 1, 3),
            date(2025, 1, 17),
            date(2025, 1, 31),
            date(2025, 2, 14),
            date(2025, 2, 28),
        ]

    def test_with_exclusions(self):
        dates = list(_generate_weekly_dates(
            start_date=date(2025, 1, 3),
            end_date=date(2025, 1, 31),
            weekday=Weekday.FRIDAY,
            exclusions={date(2025, 1, 17)},
        ))
        assert dates == [
            date(2025, 1, 3),
            date(2025, 1, 10),
            date(2025, 1, 24),
            date(2025, 1, 31),
        ]

    def test_empty_range_start_after_end(self):
        dates = list(_generate_weekly_dates(
            start_date=date(2025, 1, 31),
            end_date=date(2025, 1, 3),
            weekday=Weekday.FRIDAY,
        ))
        assert dates == []

    def test_single_date_excluded(self):
        dates = list(_generate_weekly_dates(
            start_date=date(2025, 1, 3),
            end_date=date(2025, 1, 9),
            weekday=Weekday.FRIDAY,
            exclusions={date(2025, 1, 3)},
        ))
        assert dates == []

    def test_start_date_mismatch_raises(self):
        with pytest.raises(ValueError, match="does not match weekday"):
            list(_generate_weekly_dates(
                start_date=date(2025, 1, 6),
                end_date=date(2025, 1, 31),
                weekday=Weekday.FRIDAY,
            ))


class TestGenerateDailyDates:
    def test_daily_dates(self):
        dates = list(_generate_daily_dates(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 5),
        ))
        assert dates == [
            date(2025, 1, 1),
            date(2025, 1, 2),
            date(2025, 1, 3),
            date(2025, 1, 4),
            date(2025, 1, 5),
        ]

    def test_every_other_day(self):
        dates = list(_generate_daily_dates(
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 10),
            interval=2,
        ))
        assert dates == [
            date(2025, 1, 1),
            date(2025, 1, 3),
            date(2025, 1, 5),
            date(2025, 1, 7),
            date(2025, 1, 9),
        ]


class TestExpandRecurrence:
    def test_weekly_quiz_generates_correct_fridays(self):
        recurring = RecurringEvent(
            title="Friday Quiz",
            course="CS 101",
            event_type=EventType.QUIZ,
            description="Weekly quiz",
            duration_minutes=30,
            recurrence=Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                weekday=Weekday.FRIDAY,
                start_date=date(2025, 1, 10),
                end_date=date(2025, 1, 31),
                time=dt_time(10, 0, 0),
            ),
        )

        events = expand_recurrence(recurring)

        assert len(events) == 4
        for event in events:
            assert event.due_date.weekday() == 4

        assert events[0].due_date.date() == date(2025, 1, 10)
        assert events[1].due_date.date() == date(2025, 1, 17)
        assert events[2].due_date.date() == date(2025, 1, 24)
        assert events[3].due_date.date() == date(2025, 1, 31)

        for event in events:
            assert event.due_date.hour == 10
            assert event.due_date.minute == 0

        assert events[0].title == "Friday Quiz 1"
        assert events[1].title == "Friday Quiz 2"

        assert events[0].course == "CS 101"
        assert events[0].event_type == EventType.QUIZ
        assert events[0].duration_minutes == 30
        assert events[0].time_specified is True

    def test_exclusions_respected(self):
        recurring = RecurringEvent(
            title="Quiz",
            event_type=EventType.QUIZ,
            recurrence=Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                weekday=Weekday.FRIDAY,
                start_date=date(2025, 1, 3),
                end_date=date(2025, 1, 31),
                exclusions=[date(2025, 1, 17), date(2025, 1, 24)],
            ),
        )

        events = expand_recurrence(recurring)

        dates = [e.due_date.date() for e in events]
        assert date(2025, 1, 17) not in dates
        assert date(2025, 1, 24) not in dates
        assert len(events) == 3

    def test_no_time_defaults_to_2359(self):
        recurring = RecurringEvent(
            title="Assignment",
            event_type=EventType.ASSIGNMENT,
            recurrence=Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                weekday=Weekday.MONDAY,
                start_date=date(2025, 1, 6),
                end_date=date(2025, 1, 13),
                time=None,
            ),
        )

        events = expand_recurrence(recurring)

        assert len(events) == 2
        for event in events:
            assert event.due_date.hour == 23
            assert event.due_date.minute == 59
            assert event.time_specified is False

    def test_weekly_without_weekday_raises(self):
        recurring = RecurringEvent(
            title="Quiz",
            event_type=EventType.QUIZ,
            recurrence=Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                weekday=None,
                start_date=date(2025, 1, 3),
                end_date=date(2025, 1, 31),
            ),
        )

        with pytest.raises(ValueError, match="requires weekday"):
            expand_recurrence(recurring)

    def test_weekly_start_date_must_match_weekday(self):
        recurring = RecurringEvent(
            title="Quiz",
            event_type=EventType.QUIZ,
            recurrence=Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                weekday=Weekday.FRIDAY,
                start_date=date(2025, 1, 6),
                end_date=date(2025, 1, 31),
            ),
        )

        with pytest.raises(ValueError, match="does not match weekday"):
            expand_recurrence(recurring)

    def test_single_occurrence_no_number(self):
        recurring = RecurringEvent(
            title="Final Review",
            event_type=EventType.OTHER,
            recurrence=Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                weekday=Weekday.FRIDAY,
                start_date=date(2025, 1, 10),
                end_date=date(2025, 1, 10),
            ),
        )

        events = expand_recurrence(recurring)
        assert len(events) == 1
        assert events[0].title == "Final Review"


class TestIntervalValidation:
    def test_interval_zero_rejected(self):
        with pytest.raises(ValueError):
            Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                interval=0,
                weekday=Weekday.FRIDAY,
                start_date=date(2025, 1, 3),
                end_date=date(2025, 1, 31),
            )

    def test_interval_negative_rejected(self):
        with pytest.raises(ValueError):
            Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                interval=-1,
                weekday=Weekday.FRIDAY,
                start_date=date(2025, 1, 3),
                end_date=date(2025, 1, 31),
            )


class TestMonthlyDateGeneration:
    def test_monthly_across_year_boundary(self):
        dates = list(_generate_monthly_dates(
            start_date=date(2025, 11, 15),
            end_date=date(2026, 2, 15),
            interval=1,
        ))
        assert dates == [
            date(2025, 11, 15),
            date(2025, 12, 15),
            date(2026, 1, 15),
            date(2026, 2, 15),
        ]

    def test_monthly_day_clamping(self):
        dates = list(_generate_monthly_dates(
            start_date=date(2025, 1, 31),
            end_date=date(2025, 4, 30),
            interval=1,
        ))
        assert dates == [
            date(2025, 1, 31),
            date(2025, 2, 28),
            date(2025, 3, 28),
            date(2025, 4, 28),
        ]

    def test_monthly_day_clamping_leap_year(self):
        dates = list(_generate_monthly_dates(
            start_date=date(2024, 1, 31),
            end_date=date(2024, 3, 31),
            interval=1,
        ))
        assert dates == [
            date(2024, 1, 31),
            date(2024, 2, 29),
            date(2024, 3, 29),
        ]


class TestExpandRecurrenceIntegration:
    def test_semester_of_friday_quizzes(self):
        recurring = RecurringEvent(
            title="Weekly Quiz",
            course="CS 101",
            event_type=EventType.QUIZ,
            recurrence=Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                weekday=Weekday.FRIDAY,
                start_date=date(2025, 1, 10),
                end_date=date(2025, 4, 11),
                time=dt_time(10, 0, 0),
                exclusions=[
                    date(2025, 3, 14),
                    date(2025, 3, 21),
                ],
            ),
        )

        events = expand_recurrence(recurring)

        assert len(events) == 12

        for event in events:
            assert event.due_date.weekday() == 4

        dates = [e.due_date.date() for e in events]
        assert date(2025, 3, 14) not in dates
        assert date(2025, 3, 21) not in dates


class TestExpandAllRecurrences:
    def test_skips_invalid_recurrence(self):
        valid = RecurringEvent(
            title="Valid Quiz",
            event_type=EventType.QUIZ,
            recurrence=Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                weekday=Weekday.FRIDAY,
                start_date=date(2025, 1, 3),
                end_date=date(2025, 1, 10),
            ),
        )

        invalid = RecurringEvent(
            title="Invalid Quiz",
            event_type=EventType.QUIZ,
            recurrence=Recurrence(
                frequency=RecurrenceFrequency.WEEKLY,
                weekday=Weekday.FRIDAY,
                start_date=date(2025, 1, 6),
                end_date=date(2025, 1, 31),
            ),
        )

        events = expand_all_recurrences([valid, invalid])

        assert len(events) == 2
        assert all("Valid" in e.title for e in events)
