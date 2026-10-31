"""
database/assign_rfid.py
Assigns RFID UIDs from rfid_uids.txt to the Heisenberg students, in masterlist order.
Run from attendance_system:  python -m database.assign_rfid
"""

import csv
from pathlib import Path

from database.db import init_db, execute

BASE = Path(__file__).resolve().parent
CSV_PATH = BASE / "heisenberg_students.csv"
UID_PATH = BASE / "rfid_uids.txt"


def main() -> None:
    init_db()

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        students = list(csv.DictReader(f))

    lines = [ln.strip().upper() for ln in UID_PATH.read_text(encoding="utf-8").splitlines()]
    lines = [ln for ln in lines if ln]  # drop blank lines

    if len(lines) != len(students):
        raise SystemExit(f"Expected {len(students)} lines, found {len(lines)}. Fix rfid_uids.txt.")

    real_uids = [ln for ln in lines if ln != "MISSING"]
    if len(set(real_uids)) != len(real_uids):
        raise SystemExit("Duplicate UID found. The same card is listed twice.")

    assigned = 0
    for student, uid in zip(students, lines):
        if uid == "MISSING":
            continue
        execute(
            "UPDATE students SET rfid_uid = ? WHERE student_number = ?",
            (uid, student["student_number"].strip()),
        )
        assigned += 1

    print(f"Assigned {assigned} cards. {len(students) - assigned} students have no card yet.")


if __name__ == "__main__":
    main()