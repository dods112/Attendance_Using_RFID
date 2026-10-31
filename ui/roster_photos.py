"""
ui/roster_photos.py
Photo or initials for each student in the roster table.
Photos are read from assets/students/<student_number>.jpg (or .jpeg, .png, .webp).
"""

import base64
import html
from functools import lru_cache

from config import BASE_DIR

PHOTO_DIR = BASE_DIR / "assets" / "students"
MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


@lru_cache(maxsize=256)
def photo_src(student_number: str):
    """Photo as a data URI, or None. Cached so each file is read only once."""
    for ext, mime in MIME.items():
        path = PHOTO_DIR / f"{student_number}{ext}"
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"
    return None


def initials(full_name: str) -> str:
    """'ALBORIA, SAVANNAH C.' -> 'AS'."""
    surname, _, given = full_name.partition(",")
    given_words = given.split()
    first = given_words[0] if given_words else ""
    return (surname.strip()[:1] + first[:1]).upper() or "?"


def student_cell(student_number: str, full_name: str) -> str:
    """Avatar and name, ready to drop into a table cell."""
    src = photo_src(student_number)
    if src:
        avatar = f'<img class="ros-avatar" src="{src}" alt="">'
    else:
        avatar = f'<span class="ros-avatar ros-avatar-init">{html.escape(initials(full_name))}</span>'
    return (
        '<div class="ros-student">'
        f"{avatar}"
        f'<span>{html.escape(full_name)}</span>'
        "</div>"
    )