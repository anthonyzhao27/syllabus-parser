"""Tests for LLM extraction service."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import EventType, ParsedEvent
from app.services.llm import (
    _parse_events,
    _parse_duration,
    _apply_smart_defaults,
    _apply_all_smart_defaults,
    extract_events,
)


class TestParseEvents:
    def test_parses_valid_array(self) -> None:
        raw = json.dumps(
            [
                {
                    "title": "Homework 1",
                    "due_date": "2025-01-30T23:59:00",
                    "course": "CS 101",
                    "event_type": "assignment",
                    "description": "",
                }
            ]
        )
        events = _parse_events(raw)
        assert len(events) == 1
        assert events[0].title == "Homework 1"
        assert events[0].due_date == datetime(2025, 1, 30, 23, 59)
        assert events[0].course == "CS 101"
        assert events[0].event_type == "assignment"

    def test_parses_object_with_events_key(self) -> None:
        raw = json.dumps(
            {
                "events": [
                    {
                        "title": "Midterm",
                        "due_date": "2025-03-10T14:00:00",
                        "course": "CS 101",
                        "event_type": "exam",
                        "description": "Covers chapters 1-5",
                    }
                ]
            }
        )
        events = _parse_events(raw)
        assert len(events) == 1
        assert events[0].title == "Midterm"
        assert events[0].event_type == "exam"

    def test_parses_object_with_arbitrary_key(self) -> None:
        raw = json.dumps(
            {
                "assignments": [
                    {
                        "title": "Quiz 1",
                        "due_date": "2025-02-14T23:59:00",
                        "event_type": "quiz",
                    }
                ]
            }
        )
        events = _parse_events(raw)
        assert len(events) == 1

    def test_strips_markdown_fences(self) -> None:
        raw = '```json\n[{"title": "HW1", "due_date": "2025-01-30T23:59:00"}]\n```'
        events = _parse_events(raw)
        assert len(events) == 1
        assert events[0].title == "HW1"

    def test_skips_malformed_events(self) -> None:
        raw = json.dumps(
            [
                {"title": "Good Event", "due_date": "2025-01-30T23:59:00"},
                {"title": "Bad Event", "due_date": "not-a-date"},
                {"title": "Also Good", "due_date": "2025-03-10T14:00:00"},
            ]
        )
        events = _parse_events(raw)
        assert len(events) == 2
        assert events[0].title == "Good Event"
        assert events[1].title == "Also Good"

    def test_empty_array(self) -> None:
        events = _parse_events("[]")
        assert events == []

    def test_empty_object_with_array(self) -> None:
        events = _parse_events('{"events": []}')
        assert events == []

    def test_optional_fields_default(self) -> None:
        raw = json.dumps([{"title": "HW1", "due_date": "2025-01-30T23:59:00"}])
        events = _parse_events(raw)
        assert events[0].course == ""
        assert events[0].event_type == EventType.OTHER
        assert events[0].description == ""

    def test_raises_on_total_garbage(self) -> None:
        with pytest.raises(ValueError, match="Could not parse"):
            _parse_events("this is not json at all")

    def test_raises_on_object_without_array(self) -> None:
        with pytest.raises(ValueError, match="no array field"):
            _parse_events('{"status": "ok"}')


class TestExtractEvents:
    @pytest.mark.asyncio
    async def test_calls_openai_and_returns_events(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            [
                {
                    "title": "Homework 1",
                    "due_date": "2025-01-30T23:59:00",
                    "course": "CS 101",
                    "event_type": "assignment",
                    "description": "Ch 1-3",
                },
                {
                    "title": "Midterm",
                    "due_date": "2025-03-10T14:00:00",
                    "course": "CS 101",
                    "event_type": "exam",
                    "description": "",
                },
            ]
        )

        with patch("app.services.llm.AsyncOpenAI") as MockClient:
            instance = AsyncMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            events = await extract_events("Homework 1 due Jan 30. Midterm March 10.")

            assert len(events) == 2
            assert events[0].title == "Homework 1"
            assert events[1].title == "Midterm"

            call_kwargs = instance.chat.completions.create.call_args.kwargs
            assert call_kwargs["response_format"] == {"type": "json_object"}
            assert call_kwargs["temperature"] == 0.0
            assert len(call_kwargs["messages"]) == 2
            assert call_kwargs["messages"][1]["content"] == (
                "Homework 1 due Jan 30. Midterm March 10."
            )

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty_list(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"events": []}'

        with patch("app.services.llm.AsyncOpenAI") as MockClient:
            instance = AsyncMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            events = await extract_events("This syllabus has no dates.")
            assert events == []

    @pytest.mark.asyncio
    async def test_raises_on_api_failure(self) -> None:
        with patch("app.services.llm.AsyncOpenAI") as MockClient:
            instance = AsyncMock()
            instance.chat.completions.create = AsyncMock(
                side_effect=Exception("API rate limit")
            )
            MockClient.return_value = instance

            with pytest.raises(Exception, match="API rate limit"):
                await extract_events("some text")

    @pytest.mark.asyncio
    async def test_raises_value_error_on_bad_json(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json"

        with patch("app.services.llm.AsyncOpenAI") as MockClient:
            instance = AsyncMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            with pytest.raises(ValueError):
                await extract_events("some text")


class TestParseDuration:
    def test_positive_integer(self):
        assert _parse_duration(120) == 120

    def test_positive_integer_string(self):
        assert _parse_duration("90") == 90

    def test_positive_float_truncates(self):
        assert _parse_duration(90.5) == 90

    def test_hours(self):
        assert _parse_duration("2 hours") == 120

    def test_hour_singular(self):
        assert _parse_duration("1 hour") == 60

    def test_hrs_abbreviation(self):
        assert _parse_duration("2 hrs") == 120

    def test_h_abbreviation(self):
        assert _parse_duration("2h") == 120

    def test_minutes(self):
        assert _parse_duration("90 minutes") == 90

    def test_min_abbreviation(self):
        assert _parse_duration("45 min") == 45

    def test_mins_abbreviation(self):
        assert _parse_duration("30 mins") == 30

    def test_fractional_hours(self):
        assert _parse_duration("1.5 hours") == 90

    def test_whitespace_tolerance(self):
        assert _parse_duration("  2  hours  ") == 120

    def test_zero_returns_none(self):
        assert _parse_duration(0) is None

    def test_negative_returns_none(self):
        assert _parse_duration(-30) is None

    def test_zero_string_returns_none(self):
        assert _parse_duration("0") is None

    def test_none_returns_none(self):
        assert _parse_duration(None) is None

    def test_garbage_string_returns_none(self):
        assert _parse_duration("sometime") is None

    def test_empty_string_returns_none(self):
        assert _parse_duration("") is None


class TestSmartDefaults:
    def test_preserves_explicit_duration(self):
        event = ParsedEvent(
            title="Midterm",
            due_date=datetime(2025, 2, 15, 14, 0),
            event_type=EventType.EXAM,
            time_specified=True,
            duration_minutes=120,
        )
        result = _apply_smart_defaults(event)
        assert result.duration_minutes == 120
        assert result.due_date == datetime(2025, 2, 15, 14, 0)

    def test_all_day_no_duration(self):
        event = ParsedEvent(
            title="Homework 1",
            due_date=datetime(2025, 1, 30, 23, 59),
            event_type=EventType.ASSIGNMENT,
            time_specified=False,
            duration_minutes=None,
        )
        result = _apply_smart_defaults(event)
        assert result.duration_minutes is None
        assert result.due_date == datetime(2025, 1, 30, 23, 59)

    def test_2359_deadline_adjusted(self):
        event = ParsedEvent(
            title="Homework 1",
            due_date=datetime(2025, 1, 30, 23, 59, 0),
            event_type=EventType.ASSIGNMENT,
            time_specified=True,
            duration_minutes=None,
        )
        result = _apply_smart_defaults(event)
        assert result.due_date == datetime(2025, 1, 30, 23, 30, 0)
        assert result.duration_minutes == 30

    def test_2359_exam_not_adjusted(self):
        event = ParsedEvent(
            title="Late Night Exam",
            due_date=datetime(2025, 1, 30, 23, 59, 0),
            event_type=EventType.EXAM,
            time_specified=True,
            duration_minutes=None,
        )
        result = _apply_smart_defaults(event)
        assert result.due_date == datetime(2025, 1, 30, 23, 59, 0)
        assert result.duration_minutes == 120

    def test_2358_not_adjusted(self):
        event = ParsedEvent(
            title="Homework",
            due_date=datetime(2025, 1, 30, 23, 58, 0),
            event_type=EventType.ASSIGNMENT,
            time_specified=True,
            duration_minutes=None,
        )
        result = _apply_smart_defaults(event)
        assert result.due_date == datetime(2025, 1, 30, 23, 58, 0)
        assert result.duration_minutes == 30

    def test_exam_default_duration(self):
        event = ParsedEvent(
            title="Midterm",
            due_date=datetime(2025, 2, 15, 14, 0),
            event_type=EventType.EXAM,
            time_specified=True,
            duration_minutes=None,
        )
        result = _apply_smart_defaults(event)
        assert result.duration_minutes == 120

    def test_quiz_default_duration(self):
        event = ParsedEvent(
            title="Quiz 1",
            due_date=datetime(2025, 1, 17, 10, 0),
            event_type=EventType.QUIZ,
            time_specified=True,
            duration_minutes=None,
        )
        result = _apply_smart_defaults(event)
        assert result.duration_minutes == 30

    def test_presentation_default_duration(self):
        event = ParsedEvent(
            title="Final Presentation",
            due_date=datetime(2025, 4, 10, 14, 0),
            event_type=EventType.PRESENTATION,
            time_specified=True,
            duration_minutes=None,
        )
        result = _apply_smart_defaults(event)
        assert result.duration_minutes == 30

    def test_assignment_default_duration(self):
        event = ParsedEvent(
            title="Project Milestone",
            due_date=datetime(2025, 3, 1, 17, 0),
            event_type=EventType.ASSIGNMENT,
            time_specified=True,
            duration_minutes=None,
        )
        result = _apply_smart_defaults(event)
        assert result.duration_minutes == 30


class TestApplyAllSmartDefaults:
    def test_applies_to_all_events(self):
        events = [
            ParsedEvent(
                title="Exam",
                due_date=datetime(2025, 2, 15, 14, 0),
                event_type=EventType.EXAM,
                time_specified=True,
                duration_minutes=None,
            ),
            ParsedEvent(
                title="Quiz",
                due_date=datetime(2025, 1, 17, 10, 0),
                event_type=EventType.QUIZ,
                time_specified=True,
                duration_minutes=None,
            ),
        ]
        results = _apply_all_smart_defaults(events)
        assert results[0].duration_minutes == 120
        assert results[1].duration_minutes == 30


class TestExtractEventsPostProcessing:
    @pytest.mark.asyncio
    async def test_duration_preserved_from_llm(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {
                        "title": "Midterm",
                        "due_date": "2025-02-15T14:00:00",
                        "event_type": "exam",
                        "time_specified": True,
                        "duration_minutes": 120,
                    }
                ]
            }
        )

        with patch("app.services.llm.AsyncOpenAI") as MockClient:
            instance = AsyncMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            events = await extract_events("Midterm on Feb 15, 2 hours")

            assert len(events) == 1
            assert events[0].duration_minutes == 120
            assert events[0].due_date.hour == 14
            assert events[0].due_date.minute == 0

    @pytest.mark.asyncio
    async def test_natural_language_duration_parsed(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {
                        "title": "Midterm",
                        "due_date": "2025-02-15T14:00:00",
                        "event_type": "exam",
                        "time_specified": True,
                        "duration_minutes": "2 hours",
                    }
                ]
            }
        )

        with patch("app.services.llm.AsyncOpenAI") as MockClient:
            instance = AsyncMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            events = await extract_events("Midterm, 2 hours")

            assert events[0].duration_minutes == 120

    @pytest.mark.asyncio
    async def test_2359_deadline_adjusted(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {
                        "title": "Homework 1",
                        "due_date": "2025-01-30T23:59:00",
                        "event_type": "assignment",
                        "time_specified": True,
                        "duration_minutes": None,
                    }
                ]
            }
        )

        with patch("app.services.llm.AsyncOpenAI") as MockClient:
            instance = AsyncMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            events = await extract_events("HW1 due Jan 30 at 11:59 PM")

            assert len(events) == 1
            assert events[0].due_date.hour == 23
            assert events[0].due_date.minute == 30
            assert events[0].duration_minutes == 30

    @pytest.mark.asyncio
    async def test_zero_duration_normalized_to_default(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {
                        "title": "Quiz",
                        "due_date": "2025-01-17T10:00:00",
                        "event_type": "quiz",
                        "time_specified": True,
                        "duration_minutes": 0,
                    }
                ]
            }
        )

        with patch("app.services.llm.AsyncOpenAI") as MockClient:
            instance = AsyncMock()
            instance.chat.completions.create = AsyncMock(return_value=mock_response)
            MockClient.return_value = instance

            events = await extract_events("Quiz")

            assert events[0].duration_minutes == 30
