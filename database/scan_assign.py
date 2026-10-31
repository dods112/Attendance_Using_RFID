"""
database/scan_assign.py
Reads card UIDs from the Arduino and assigns each one to the next Heisenberg
student who has no card yet. Progress is saved to the database after every
scan, so you can stop with Ctrl+C and resume later.
Run from attendance_system:  python -m database.scan_assign
"""

import re
import time

import serial

from config import SERIAL_PORT, BAUD_RATE
from database.db import init_db, query_all, query_one, execute

SECTION_NAME = "Heisenberg"

# Matches 4 or more hex bytes, with or without spaces or colons between them.
UID_RE = re.compile(r"((?:[0-9A-Fa-f]{2}[ :-]?){4,})")


def extract_uid(line: str) -> str | None:
    """Pull the card UID out of one line from the Arduino, e.g. 'UID: A1 B2 C3 D4' -> 'A1B2C3D4'."""
    match = UID_RE.search(line)
    if not match:
        return None
    return re.sub(r"[ :-]", "", match.group(1)).upper()


def pending_students() -> list:
    """Heisenberg students without a card, in the same order as the masterlist."""
    return query_all(
        """
        SELECT s.id, s.student_number, s.full_name
        FROM students s
        JOIN sections sec ON sec.id = s.section_id
        WHERE sec.name = ? AND s.rfid_uid IS NULL
        ORDER BY s.id
        """,
        (SECTION_NAME,),
    )


def main() -> None:
    init_db()
    queue = pending_students()
    total = query_one(
        "SELECT COUNT(*) AS n FROM students s JOIN sections sec ON sec.id = s.section_id "
        "WHERE sec.name = ?",
        (SECTION_NAME,),
    )["n"]
    done_before = total - len(queue)

    if not queue:
        print("All students already have cards. Nothing to do.")
        return

    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    except serial.SerialException as err:
        raise SystemExit(f"Could not open {SERIAL_PORT}: {err}\n"
                         "Close the Arduino Serial Monitor and try again.")

    time.sleep(2)  # the Uno resets when the port opens; give it a moment
    ser.reset_input_buffer()

    index = 0
    last_uid = None
    print(f"Connected to {SERIAL_PORT}. Tap cards in masterlist order. Ctrl+C to stop.\n")

    try:
        while index < len(queue):
            student = queue[index]
            number = done_before + index + 1
            print(f"Next: [{number}/{total}] {student['full_name']}  ({student['student_number']})",
                  flush=True)

            # Wait for a card that is not the same one we just handled.
            while True:
                raw = ser.readline().decode("utf-8", errors="ignore").strip()
                uid = extract_uid(raw)
                if uid is None or uid == last_uid:
                    continue

                owner = query_one(
                    "SELECT full_name FROM students WHERE rfid_uid = ?", (uid,)
                )
                if owner is not None:
                    print(f"  Card {uid} is already assigned to {owner['full_name']}. "
                          "Tap a different card.", flush=True)
                    last_uid = uid
                    continue

                execute(
                    "UPDATE students SET rfid_uid = ? WHERE id = ?",
                    (uid, student["id"]),
                )
                print(f"  Saved {uid} -> {student['full_name']}\n", flush=True)
                last_uid = uid
                index += 1
                break

        print("All students now have cards.")
    except KeyboardInterrupt:
        print("\nStopped. Progress is saved; run the script again to continue.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()