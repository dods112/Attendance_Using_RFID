"""
database/users.py
Functions for creating users with hashed passwords.
"""

import bcrypt

from database.db import execute, query_one


def create_user(username: str, password: str, full_name: str, role: str) -> int:
    """
    Create a user. Role must be 'admin' or 'teacher'.
    The password is hashed with bcrypt before it is stored.
    """
    if role not in ("admin", "teacher"):
        raise ValueError("role must be 'admin' or 'teacher'")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    return execute(
        "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
        (username, password_hash, full_name, role),
    )


def verify_login(username: str, password: str):
    """
    Check a username and password.
    Returns the user row if correct, or None if not.
    """
    user = query_one("SELECT * FROM users WHERE username = ?", (username,))
    if user is None:
        return None
    if bcrypt.checkpw(password.encode("utf-8"), user["password_hash"].encode("utf-8")):
        return user
    return None