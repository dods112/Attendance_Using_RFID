"""
services/attendance_service.py
Records card scans and builds the live roster for a class.
Class times come from database/schedule.py, so each weekday can have its own window.
"""

import csv
import io
import sqlite3
from datetime import datetime

from config import GRACE_MINUTES
from database.db import execute, query_all, query_one
from database.schedule import get_window


def current_period() -> str:
    """AM before noon, PM from noon onward."""
    return "AM" if datetime.now().hour < 12 else "PM"


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def record_scan(uid: str, class_offering_id: int) -> dict:
    """
    Save one card tap for the active class.
    Returns a result: PRESENT, LATE, OUTSIDE CLASS TIME, ALREADY RECORDED,
    UNREGISTERED, or WRONG CLASS.
    """
    student = query_one(
        "SELECT id, full_name, section_id FROM students WHERE rfid_uid = ?", (uid,)
    )
    if student is None:
        return {"result": "UNREGISTERED"}

    offering = query_one(
        "SELECT section_id FROM class_offerings WHERE id = ?", (class_offering_id,)
    )
    if offering is None or offering["section_id"] != student["section_id"]:
        return {"result": "WRONG CLASS", "name": student["full_name"]}

    now = datetime.now()
    now_min = now.hour * 60 + now.minute

    window = get_window(class_offering_id, now.date())
    if window is None:
        # No class today, or outside the window. Nothing is saved.
        return {"result": "OUTSIDE CLASS TIME", "name": student["full_name"]}

    start, end = window
    if end and now_min > _to_minutes(end):
        return {"result": "OUTSIDE CLASS TIME", "name": student["full_name"]}

    if start:
        status = "PRESENT" if now_min <= _to_minutes(start) + GRACE_MINUTES else "LATE"
    else:
        status = "PRESENT"

    try:
        execute(
            "INSERT INTO attendance "
            "(student_id, class_offering_id, attendance_date, period, time_in, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                student["id"],
                class_offering_id,
                now.date().isoformat(),
                current_period(),
                now.strftime("%H:%M:%S"),
                status,
            ),
        )
    except sqlite3.IntegrityError:
        return {"result": "ALREADY RECORDED", "name": student["full_name"]}

    return {"result": status, "name": student["full_name"]}


def get_roster(class_offering_id: int) -> list[dict]:
    """Every student in the class's section, with status for today's current period."""
    today = datetime.now().date().isoformat()
    rows = query_all(
        """
        SELECT s.student_number,
               s.full_name,
               COALESCE(a.status, 'ABSENT') AS status,
               a.time_in
        FROM class_offerings c
        JOIN students s ON s.section_id = c.section_id
        LEFT JOIN attendance a
               ON a.student_id = s.id
              AND a.class_offering_id = c.id
              AND a.attendance_date = ?
              AND a.period = ?
        WHERE c.id = ?
        ORDER BY s.full_name
        """,
        (today, current_period(), class_offering_id),
    )
    return [
        {
            "Student No.": r["student_number"],
            "Name": r["full_name"],
            "Status": r["status"],
            "Time In": r["time_in"] or "",
        }
        for r in rows
    ]


def roster_csv(class_offering_id: int) -> str:
    """Return the current roster as CSV text, ready to download."""
    roster = get_roster(class_offering_id)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["Student No.", "Name", "Status", "Time In"])
    writer.writeheader()
    writer.writerows(roster)
    return buffer.getvalue()