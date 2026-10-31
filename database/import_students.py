"""
database/import_students.py
Imports the Heisenberg students from heisenberg_students.csv.
Safe to run again: students already in the database are skipped.
Run from attendance_system:  python -m database.import_students
"""

import csv
from pathlib import Path

from database.db import init_db, query_one, execute

CSV_PATH = Path(__file__).resolve().parent / "heisenberg_students.csv"
SECTION_NAME = "Heisenberg"


def main() -> None:
    init_db()

    section = query_one("SELECT id FROM sections WHERE name = ?", (SECTION_NAME,))
    if section is None:
        raise SystemExit(f"Section not found: {SECTION_NAME}")

    added = 0
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            execute(
                "INSERT OR IGNORE INTO students (student_number, full_name, section_id) "
                "VALUES (?, ?, ?)",
                (row["student_number"].strip(), row["full_name"].strip(), section["id"]),
            )
            added += 1

    total = query_one(
        "SELECT COUNT(*) AS n FROM students WHERE section_id = ?", (section["id"],)
    )["n"]
    print(f"Processed {added} rows. Heisenberg now has {total} students.")


if __name__ == "__main__":
    main()