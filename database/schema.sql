-- database/schema.sql
-- Creates all tables. Safe to run again because of IF NOT EXISTS.

PRAGMA foreign_keys = ON;

-- Admin login accounts. Only the admin logs in with a username and password.
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    full_name     TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('admin', 'teacher')),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Sections such as Heisenberg and Bronsted.
CREATE TABLE IF NOT EXISTS sections (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Students belong to one section. rfid_uid is optional until a card is assigned.
CREATE TABLE IF NOT EXISTS students (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    student_number TEXT    NOT NULL UNIQUE,
    full_name      TEXT    NOT NULL,
    section_id     INTEGER NOT NULL REFERENCES sections(id) ON DELETE RESTRICT,
    rfid_uid       TEXT    UNIQUE,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- Subjects such as Research 1, Chem 1, Emtec 1, Advance Math.
CREATE TABLE IF NOT EXISTS subjects (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    created_at TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- One-off changes for a specific date. start_time NULL means no class on that date.
CREATE TABLE IF NOT EXISTS class_date_overrides (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    class_offering_id INTEGER NOT NULL REFERENCES class_offerings(id) ON DELETE CASCADE,
    override_date     TEXT    NOT NULL,   -- YYYY-MM-DD
    start_time        TEXT,
    end_time          TEXT,
    UNIQUE (class_offering_id, override_date)
);
-- Per-day schedule overrides. A missing row means the default times apply.
-- start_time NULL means no class on that day.
CREATE TABLE IF NOT EXISTS class_schedules (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    class_offering_id INTEGER NOT NULL REFERENCES class_offerings(id) ON DELETE CASCADE,
    weekday           INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),   -- 0 = Monday
    start_time        TEXT,                                               -- e.g. "12:20"
    end_time          TEXT,                                               -- e.g. "13:50"
    UNIQUE (class_offering_id, weekday)
);
-- A class is one section taking one subject with one teacher.
-- access_code is what the teacher types on the login page.
CREATE TABLE IF NOT EXISTS class_offerings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id   INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    subject_id   INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    teacher_name TEXT    NOT NULL,
    access_code  TEXT    NOT NULL UNIQUE,
    start_time   TEXT,                       -- e.g. "12:20"
    end_time     TEXT,                       -- e.g. "13:50"
    created_at   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (section_id, subject_id)
);

-- One row per student per class per day per period (AM or PM).
CREATE TABLE IF NOT EXISTS attendance (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id        INTEGER NOT NULL REFERENCES students(id)        ON DELETE CASCADE,
    class_offering_id INTEGER NOT NULL REFERENCES class_offerings(id) ON DELETE CASCADE,
    attendance_date   TEXT    NOT NULL,                       -- YYYY-MM-DD
    period            TEXT    NOT NULL CHECK (period IN ('AM', 'PM')),
    time_in           TEXT    NOT NULL,                       -- HH:MM:SS
    status            TEXT    NOT NULL CHECK (status IN ('PRESENT', 'LATE')),
    created_at        TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (student_id, class_offering_id, attendance_date, period)
);

-- Indexes for the lookups the dashboard does most often.
CREATE INDEX IF NOT EXISTS idx_students_section    ON students(section_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date     ON attendance(attendance_date);
CREATE INDEX IF NOT EXISTS idx_attendance_offering ON attendance(class_offering_id);

-- Starter data so the dropdowns are never empty.
INSERT OR IGNORE INTO sections (name) VALUES ('Heisenberg'), ('Bronsted');
INSERT OR IGNORE INTO subjects (name) VALUES
    ('Research 1'),
    ('Chem 1'),
    ('Emtec 1'),
    ('Advance Math');