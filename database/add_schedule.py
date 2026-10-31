"""
database/add_schedule.py
Adds start and end times to existing classes, sets the Heisenberg schedule,
and clears today's test scans. Keeps all students and RFID cards.
Safe to run again. Run from attendance_system:  python -m database.add_schedule
"""

from database.db import get_connection

SCHEDULE = {
    "Research 1":   ("12:20", "13:50"),
    "Chem 1":       ("13:50", "15:20"),
    "Emtec 1":      ("15:30", "17:00"),
    "Advance Math": ("17:00", "18:30"),
}


def main() -> None:
    conn = get_connection()
    try:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(class_offerings)")}
        if "start_time" not in columns:
            conn.execute("ALTER TABLE class_offerings ADD COLUMN start_time TEXT")
            print("Added start_time column")
        if "end_time" not in columns:
            conn.execute("ALTER TABLE class_offerings ADD COLUMN end_time TEXT")
            print("Added end_time column")

        for subject, (start, end) in SCHEDULE.items():
            conn.execute(
                """
                UPDATE class_offerings SET start_time = ?, end_time = ?
                WHERE subject_id = (SELECT id FROM subjects WHERE name = ?)
                  AND section_id = (SELECT id FROM sections WHERE name = 'Heisenberg')
                """,
                (start, end, subject),
            )

        cleared = conn.execute(
            "DELETE FROM attendance WHERE attendance_date = date('now', 'localtime')"
        ).rowcount
        conn.commit()
        print(f"Schedule set. Cleared {cleared} scans from today.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()