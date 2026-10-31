"""
database/classes.py
Creates classes with access codes and looks them up when a teacher logs in.
"""

import secrets

from database.db import execute, query_one

# Letters and digits without look-alikes (no 0, O, 1, I) so codes are easy to read and type.
_CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_access_code(section_name: str, subject_name: str) -> str:
    """Build a code such as HEI-CHEM1-4K7P."""
    section_part = "".join(ch for ch in section_name.upper() if ch.isalnum())[:3]
    subject_part = "".join(ch for ch in subject_name.upper() if ch.isalnum())[:6]

    while True:
        random_part = "".join(secrets.choice(_CODE_CHARS) for _ in range(4))
        code = f"{section_part}-{subject_part}-{random_part}"
        if query_one("SELECT 1 FROM class_offerings WHERE access_code = ?", (code,)) is None:
            return code


def create_class(section_name: str, subject_name: str, teacher_name: str,
                 start_time: str, end_time: str) -> str:
    """
    Create one class and return its access code.
    Times are HH:MM strings, such as "12:20".
    """
    section = query_one("SELECT id FROM sections WHERE name = ?", (section_name,))
    subject = query_one("SELECT id FROM subjects WHERE name = ?", (subject_name,))
    if section is None:
        raise ValueError(f"Section not found: {section_name}")
    if subject is None:
        raise ValueError(f"Subject not found: {subject_name}")

    code = generate_access_code(section_name, subject_name)
    execute(
        "INSERT INTO class_offerings "
        "(section_id, subject_id, teacher_name, access_code, start_time, end_time) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (section["id"], subject["id"], teacher_name, code, start_time, end_time),
    )
    return code


def class_exists(section_name: str, subject_name: str) -> bool:
    """True if this section already has this subject set up."""
    row = query_one(
        """
        SELECT 1 FROM class_offerings c
        JOIN sections s ON s.id = c.section_id
        JOIN subjects j ON j.id = c.subject_id
        WHERE s.name = ? AND j.name = ?
        """,
        (section_name, subject_name),
    )
    return row is not None


def get_class_by_code(code: str):
    """Find the class for a typed code, or None if the code is wrong."""
    code = code.strip().upper()
    if not code:
        return None
    return query_one(
        """
        SELECT c.id, c.teacher_name, c.access_code, c.start_time, c.end_time,
               s.name AS section, j.name AS subject
        FROM class_offerings c
        JOIN sections s ON s.id = c.section_id
        JOIN subjects j ON j.id = c.subject_id
        WHERE c.access_code = ?
        """,
        (code,),
    )