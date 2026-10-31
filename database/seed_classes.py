"""
database/seed_classes.py
Creates the Heisenberg classes with teachers and schedule, then prints the access codes.
Run from attendance_system:  python -m database.seed_classes
"""

from database.db import init_db
from database.classes import create_class, class_exists

# (section, subject): (teacher, start, end)
TEACHERS = {
    ("Heisenberg", "Research 1"):   ("Sir Mark Segundino", "12:20", "13:50"),
    ("Heisenberg", "Chem 1"):       ("Ma'am Arlyn Patino", "13:50", "15:20"),
    ("Heisenberg", "Emtec 1"):      ("Sir Ken Campos", "15:30", "17:00"),
    ("Heisenberg", "Advance Math"): ("Ma'am Analyn Febrio", "17:00", "18:30"),
}


def main() -> None:
    init_db()
    print(f"{'SECTION':<12}{'SUBJECT':<16}{'TEACHER':<24}{'TIME':<14}ACCESS CODE")
    print("-" * 80)

    for (section, subject), (teacher, start, end) in TEACHERS.items():
        if class_exists(section, subject):
            print(f"{section:<12}{subject:<16}(already exists, skipped)")
            continue
        code = create_class(section, subject, teacher, start, end)
        print(f"{section:<12}{subject:<16}{teacher:<24}{start}-{end:<9}{code}")


if __name__ == "__main__":
    main()