"""
config.py
Central settings for the attendance system.
Change values here instead of hunting through the code.
"""

from pathlib import Path

# --- Project paths ---
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database" / "attendance.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"
CSS_PATH = BASE_DIR / "assets" / "style.css"

# --- Arduino serial settings ---
# On Windows, check Device Manager > Ports (COM & LPT) to find your port.
SERIAL_PORT = "COM7"
BAUD_RATE = 9600
SERIAL_RECONNECT_SECONDS = 3   # wait time before retrying a lost connection

# --- Attendance rules ---
CLASS_START_TIME = "07:30"     # classes start at this time
LATE_CUTOFF_TIME = "07:45"     # scans after this time are marked LATE

# --- App info ---
APP_TITLE = "RFID Attendance System"
APP_ICON = "📋"

GRACE_MINUTES = 10             # scans within this many minutes after start count as PRESENT