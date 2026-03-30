"""LLM prompt templates for syllabus parsing and reminders."""

EXTRACTION_PROMPT = """\
You are an expert at reading college course syllabi and extracting structured \
schedule data.

Given the text of a syllabus, extract ALL assignments, exams, quizzes, \
projects, and other graded/scheduled events WITH THEIR DUE DATES. \
Do NOT extract posting/release dates - only deadlines matter.

Rules:
1. Return a JSON object with "events" and "recurring_events" arrays.
2. For ONE-TIME events, add to "events" array with these fields:
   - "title" (string): name of the assignment or event
   - "due_date" (string): ISO 8601 datetime, e.g. "2025-01-30T23:59:00"
   - "course" (string): course name/number if mentioned, else ""
   - "event_type" (string): one of "assignment", "exam", "quiz", "project", \
"lab", "presentation", "milestone", "deadline", "discussion", "other"
   - "description" (string): brief description if available, else ""
   - "time_specified" (boolean): true if syllabus explicitly states a time
   - "duration_minutes" (integer or null): duration if explicitly stated

3. For RECURRING events (e.g., "weekly quizzes every Friday"), add to \
"recurring_events" array with these fields:
   - "title" (string): name pattern, e.g. "Friday Quiz"
   - "course" (string): course name/number
   - "event_type" (string): same options as above
   - "description" (string): brief description
   - "duration_minutes" (integer or null): duration if stated
   - "recurrence" (object):
     - "frequency" (string): "daily", "weekly", or "monthly"
     - "interval" (integer): 1 for every week, 2 for every other week, etc. Must be >= 1.
     - "weekday" (string or null): "monday" through "sunday" (required for weekly frequency)
     - "start_date" (string): first ACTUAL occurrence date (not semester start), ISO format \
"YYYY-MM-DD". For weekly patterns, this date MUST already fall on the specified weekday. \
For every-other-week patterns, use "frequency": "weekly" with "interval": 2.
     - "end_date" (string): last possible date (semester end), ISO format
     - "time" (string or null): time of day if specified, "HH:MM:SS" format
     - "exclusions" (array of strings): dates to skip, ISO format

4. If only a date is given with no time, use 23:59:00 and set time_specified=false.
5. If a specific time is stated, set time_specified=true.
6. If the year is not stated, infer from context or use current year.
7. Skip non-graded items (office hours, reading lists, policies).
8. ONLY extract DUE DATES and DEADLINES. Do NOT extract:
   - Posting dates (e.g., "HW01 posted on Friday")
   - Release dates (e.g., "Assignment released Jan 10")
   - Available dates (e.g., "Quiz available starting Monday")
   If an item has both a posted date and a due date, only extract the due date.
9. For monthly recurrence, only extract same-day-of-month patterns. Do not emit \
monthly weekday patterns such as "first Friday" or "second Tuesday".
10. If no events found, return: {"events": [], "recurring_events": []}

Example output:
{
  "events": [
    {
      "title": "Midterm Exam",
      "due_date": "2025-02-15T14:00:00",
      "course": "CS 101",
      "event_type": "exam",
      "description": "Covers chapters 1-5",
      "time_specified": true,
      "duration_minutes": 120
    }
  ],
  "recurring_events": [
    {
      "title": "Friday Quiz",
      "course": "CS 101",
      "event_type": "quiz",
      "description": "Weekly quiz on readings",
      "duration_minutes": 30,
      "recurrence": {
        "frequency": "weekly",
        "interval": 1,
        "weekday": "friday",
        "start_date": "2025-01-10",
        "end_date": "2025-04-11",
        "time": "10:00:00",
        "exclusions": ["2025-02-21", "2025-03-14"]
      }
    }
  ]
}
"""

REMINDER_PROMPT = """You are a supportive college friend sending a text reminder. Write a short, casual, encouraging SMS reminder about an upcoming deadline.

Assignment: {title}
Due: {due_date}
Course: {course}

Keep it under 160 characters. Be friendly and motivating, not annoying.
"""
