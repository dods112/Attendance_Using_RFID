"""
services/serial_service.py
Reads card UIDs from the Arduino in a background thread, records each scan
for the active class, and sends the result back to the LCD and buzzer.
"""

import re
import threading
import time
from collections import deque
from datetime import datetime

import serial

from services.attendance_service import record_scan

UID_RE = re.compile(r"((?:[0-9A-Fa-f]{2}[ :-]?){4,})")


def extract_uid(line: str) -> str | None:
    """Pull the card UID out of one line from the Arduino, e.g. 'UID:A1B2C3D4'."""
    match = UID_RE.search(line)
    if not match:
        return None
    return re.sub(r"[ :-]", "", match.group(1)).upper()


def ascii_only(text: str) -> str:
    """The LCD can't show letters like Ñ, so remove them."""
    return text.encode("ascii", "ignore").decode("ascii")


def surname(full_name: str) -> str:
    """'ANIÑON, KIM JACOB U.' -> 'ANION'"""
    return ascii_only(full_name.split(",")[0]).strip()


def lcd_message(result: dict) -> tuple[str, str]:
    """Turn a scan result into the two LCD lines (each at most 16 characters)."""
    outcome = result["result"]
    name = surname(result.get("name", ""))

    if outcome == "PRESENT":
        return "ATTENDANCE SAVED", name
    if outcome == "LATE":
        return "LATE - SAVED", name
    if outcome == "ALREADY RECORDED":
        return "ALREADY RECORDED", name
    if outcome == "OUTSIDE CLASS TIME":
        return "OUTSIDE CLASS", "TIME"
    if outcome == "WRONG CLASS":
        return "WRONG CLASS", name
    return "UNKNOWN CARD", "PLEASE REGISTER"


class SerialReader:
    def __init__(self, port: str, baud: int, reconnect_seconds: int):
        self.port = port
        self.baud = baud
        self.reconnect_seconds = reconnect_seconds
        self.active_class_id: int | None = None
        self.connected = False
        self.last_error = ""
        self.events: deque = deque(maxlen=50)
        self.popup_queue: deque = deque(maxlen=100)
        self._ser: serial.Serial | None = None
        self._write_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                with serial.Serial(self.port, self.baud, timeout=1) as ser:
                    self._ser = ser
                    time.sleep(2)  # the Uno resets when the port opens
                    ser.reset_input_buffer()
                    self.connected = True
                    self.last_error = ""
                    while not self._stop.is_set():
                        raw = ser.readline().decode("utf-8", errors="ignore")
                        uid = extract_uid(raw)
                        if uid:
                            self._handle(uid)
            except (serial.SerialException, OSError) as err:
                # Covers an unplugged cable or a busy port. Retry after a delay.
                self.last_error = str(err)
                self._stop.wait(self.reconnect_seconds)
            finally:
                self._ser = None
                self.connected = False

    def simulate_scan(self, uid: str) -> None:
        """Run a card tap without the Arduino. Same path as a real scan."""
        self._handle(uid)

    def send_lcd(self, line1: str, line2: str) -> None:
        """Send a message to the Arduino. It shows on the LCD and sounds the buzzer."""
        ser = self._ser
        if ser is None:
            return
        message = f"LCD|{line1[:16]}|{line2[:16]}\n"
        with self._write_lock:
            try:
                ser.write(message.encode("ascii", "ignore"))
            except (serial.SerialException, OSError):
                pass

    def _handle(self, uid: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")

        if self.active_class_id is None:
            event = {"Time": stamp, "Card": uid, "Result": "NO CLASS ACTIVE", "Name": ""}
            self.events.appendleft(event)
            self.popup_queue.append({**event, "added": time.time()})
            self.send_lcd("NO CLASS", "LOG IN FIRST")
            return

        result = record_scan(uid, self.active_class_id)
        line1, line2 = lcd_message(result)
        self.send_lcd(line1, line2)

        event = {
            "Time": stamp,
            "Card": uid,
            "Result": result["result"],
            "Name": result.get("name", ""),
        }
        self.events.appendleft(event)
        self.popup_queue.append({**event, "added": time.time()})