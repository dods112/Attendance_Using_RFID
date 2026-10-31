"""
database/schedule.py
Flexible class schedules. Each class can have its own time window for each weekday.
If a class has no row for a day, its default times from class_offerings are used.
A row with no start time means no class that day.

Admin commands (run from attendance_system):
  python -m database.schedule show HEI-RESEAR-FUUW
  python -m database.schedule set HEI-RESEAR-FUUW mon-fri 12:20 13:50
  python -m database.schedule set HEI-RESEAR-FUUW sat 08:00 10:00
  python -m database.schedule off HEI-RESEAR-FUUW sat-sun
  python -m database.schedule clear HEI-RESEAR-FUUW sat
"""

import argparse
from datetime import date, datetime

from database.db import execute, query_all, query_one

DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def ensure_table() -> None:
    """Create the schedule tables if they don't exist yet."""
    execute(
        """
        CREATE TABLE IF NOT EXISTS class_schedules (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            class_offering_id INTEGER NOT NULL REFERENCES class_offerings(id) ON DELETE CASCADE,
            weekday           INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
            start_time        TEXT,
            end_time          TEXT,
            UNIQUE (class_offering_id, weekday)
        )
        """
    )
    execute(
        """
        CREATE TABLE IF NOT EXISTS class_date_overrides (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            class_offering_id INTEGER NOT NULL REFERENCES class_offerings(id) ON DELETE CASCADE,
            override_date     TEXT    NOT NULL,
            start_time        TEXT,
            end_time          TEXT,
            UNIQUE (class_offering_id, override_date)
        )
        """
    )


def parse_days(text: str) -> list[int]:
    """'mon-fri' -> [0..4], 'sat,sun' -> [5, 6], 'all' -> every day."""
    text = text.lower().strip()
    if text == "all":
        return list(range(7))
    days = set()
    for part in text.split(","):
        part = part.strip()
        if "-" in part:
            first, last = part.split("-", 1)
            days.update(range(DAY_NAMES.index(first), DAY_NAMES.index(last) + 1))
        else:
            days.add(DAY_NAMES.index(part))
    return sorted(days)


def _to_min(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _check_time(value: str) -> str:
    try:
        datetime.strptime(value, "%H:%M")
    except ValueError:
        raise ValueError(f"Bad time '{value}'. Use 24-hour HH:MM, for example 13:50.")
    return value


def class_id_for_code(code: str) -> int:
    row = query_one(
        "SELECT id FROM class_offerings WHERE access_code = ?", (code.strip().upper(),)
    )
    if row is None:
        raise ValueError(f"No class has the code {code}.")
    return row["id"]


def get_window(class_id: int, on_date: date | None = None):
    """
    Return the class window for a date. Checks in this order:
      1. A date-specific change (reschedule)
      2. The weekday pattern
      3. The default times
    Returns None for no class, or (start, end).
    """
    day = on_date or date.today()

    override = query_one(
        "SELECT start_time, end_time FROM class_date_overrides "
        "WHERE class_offering_id = ? AND override_date = ?",
        (class_id, day.isoformat()),
    )
    if override is not None:
        if override["start_time"] is None:
            return None
        return (override["start_time"], override["end_time"])

    custom = query_one(
        "SELECT start_time, end_time FROM class_schedules "
        "WHERE class_offering_id = ? AND weekday = ?",
        (class_id, day.weekday()),
    )
    if custom is not None:
        if custom["start_time"] is None:
            return None
        return (custom["start_time"], custom["end_time"])

    base = query_one(
        "SELECT start_time, end_time FROM class_offerings WHERE id = ?", (class_id,)
    )
    if base is None:
        return None
    return (base["start_time"], base["end_time"])


def schedule_text(class_id: int, on_date: date | None = None) -> str:
    """Readable text for the dashboard, e.g. '12:20 – 13:50' or 'No class today'."""
    window = get_window(class_id, on_date)
    if window is None:
        return "No class today"
    start, end = window
    if start is None:
        return "Open all day"
    return f"{start} – {end}"


def set_window(class_id: int, days: list[int], start: str | None, end: str | None) -> None:
    """Set a window for the given weekdays. start=None turns those days off."""
    if start is not None:
        _check_time(start)
        _check_time(end)
        if _to_min(start) >= _to_min(end):
            raise ValueError("End time must be after start time.")
    for day in days:
        execute(
            """
            INSERT INTO class_schedules (class_offering_id, weekday, start_time, end_time)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (class_offering_id, weekday)
            DO UPDATE SET start_time = excluded.start_time, end_time = excluded.end_time
            """,
            (class_id, day, start, end),
        )


def clear_window(class_id: int, days: list[int]) -> None:
    """Remove custom rows so those days use the default times again."""
    for day in days:
        execute(
            "DELETE FROM class_schedules WHERE class_offering_id = ? AND weekday = ?",
            (class_id, day),
        )


def list_schedule(class_id: int) -> list[tuple[str, str, bool]]:
    """Return (day label, text, is_custom) for all seven days."""
    custom_rows = {
        r["weekday"]: r
        for r in query_all(
            "SELECT weekday, start_time, end_time FROM class_schedules "
            "WHERE class_offering_id = ?",
            (class_id,),
        )
    }
    rows = []
    for day in range(7):
        if day in custom_rows:
            r = custom_rows[day]
            if r["start_time"] is None:
                text = "No class"
            else:
                text = f'{r["start_time"]} – {r["end_time"]}'
            rows.append((DAY_LABELS[day], text, True))
        else:
            rows.append((DAY_LABELS[day], schedule_text(class_id, _date_for_weekday(day)), False))
    return rows


def _date_for_weekday(day: int) -> date:
    """A date that falls on the given weekday in the current week."""
    today = date.today()
    return date.fromordinal(today.toordinal() - today.weekday() + day)

def set_date_override(class_id: int, on_date: date, start: str | None, end: str | None) -> None:
    """Change the window for one date. start=None means no class on that date."""
    if start is not None:
        _check_time(start)
        _check_time(end)
        if _to_min(start) >= _to_min(end):
            raise ValueError("End time must be after start time.")
    execute(
        """
        INSERT INTO class_date_overrides (class_offering_id, override_date, start_time, end_time)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (class_offering_id, override_date)
        DO UPDATE SET start_time = excluded.start_time, end_time = excluded.end_time
        """,
        (class_id, on_date.isoformat(), start, end),
    )


def restore_default_for_date(class_id: int, on_date: date) -> None:
    """Remove a date change so that date follows the weekly pattern again."""
    execute(
        "DELETE FROM class_date_overrides WHERE class_offering_id = ? AND override_date = ?",
        (class_id, on_date.isoformat()),
    )


def move_class(class_id: int, from_date: date, to_date: date, start: str, end: str) -> None:
    """Cancel the class on from_date and hold it on to_date at the given time."""
    if from_date == to_date:
        raise ValueError("Pick a different date to move the class to.")
    set_date_override(class_id, from_date, None, None)
    set_date_override(class_id, to_date, start, end)

if __name__ == "__main__":
    main()

