"""
ui/terminal.py
Command terminal in the sidebar. Type a command and press Enter.
The output appears in the Terminal panel on the dashboard.
Every command acts only on the class that is logged in.
"""

import html
from datetime import date

import streamlit as st

from config import SERIAL_PORT
from database.schedule import restore_default_for_date, schedule_text, set_date_override
from services.attendance_service import get_roster

HELP_TEXT = (
    "Commands\n"
    "  status              attendance counts and Arduino state\n"
    "  roster [status]     list students, optional: present | late | absent\n"
    "  find <text>         search by name or student number\n"
    "  scans               last 5 scans this session\n"
    "  today               today's schedule\n"
    "  cancel --yes        cancel this class today\n"
    "  restore             restore today's default schedule\n"
    "  clear               clear the terminal panel"
)


def _esc(value) -> str:
    return html.escape(str(value or ""))


def _counts(roster: list[dict]) -> dict:
    total = len(roster)
    present = sum(1 for r in roster if r["Status"] == "PRESENT")
    late = sum(1 for r in roster if r["Status"] == "LATE")
    absent = total - present - late
    pct = round((present + late) * 100 / total) if total else 0
    return {"total": total, "present": present, "late": late, "absent": absent, "pct": pct}


def _row_text(r: dict) -> str:
    return f'{r["Student No."]:<9} {r["Status"]:<8} {r["Name"]}'


def run_command(raw: str, cls: dict, reader) -> str:
    """Run one command for the active class and return the text to show."""
    parts = raw.strip().split()
    cmd = parts[0].lower()
    args = [a.lower() for a in parts[1:]]
    class_id = cls["id"]
    today = date.today()

    if cmd == "help":
        return HELP_TEXT

    if cmd == "status":
        c = _counts(get_roster(class_id))
        device = f"connected on {SERIAL_PORT}" if reader.connected else "offline"
        return (
            f"{cls['subject']} Â· {cls['section']}\n"
            f"Arduino: {device}\n"
            f"Total {c['total']}   Present {c['present']}   "
            f"Late {c['late']}   Absent {c['absent']}\n"
            f"Attendance rate: {c['pct']}%"
        )

    if cmd == "roster":
        want = args[0].upper() if args else None
        if want and want not in ("PRESENT", "LATE", "ABSENT"):
            return "Usage: roster [present|late|absent]"
        rows = [r for r in get_roster(class_id) if not want or r["Status"] == want]
        return "\n".join(_row_text(r) for r in rows) or "No students match."

    if cmd == "find":
        if not args:
            return "Usage: find <name or student number>"
        query = " ".join(args)
        hits = [
            r for r in get_roster(class_id)
            if query in r["Name"].lower() or query in r["Student No."].lower()
        ]
        return "\n".join(_row_text(r) for r in hits) or f'No student matches "{query}".'

    if cmd == "scans":
        events = list(reader.events)[:5]
        if not events:
            return "No scans this session."
        return "\n".join(
            f'{e["Time"]}  {e["Result"]:<20} {e["Name"] or e["Card"]}' for e in events
        )

    if cmd == "today":
        return f"{today:%A, %B %d}: {schedule_text(class_id)}"

    if cmd == "cancel":
        if args != ["--yes"]:
            return "This cancels today's class. To confirm, type: cancel --yes"
        set_date_override(class_id, today, None, None)
        return f"Class cancelled for {today:%B %d}. Type 'restore' to undo."

    if cmd == "restore":
        restore_default_for_date(class_id, today)
        return f"{today:%B %d}: default schedule restored ({schedule_text(class_id)})."

    return f'Unknown command: "{cmd}". Type "help" for the list.'


def show_terminal_input(reader, cls: dict):
    """Command box in the sidebar. Enter runs the command and clears the box."""
    with st.sidebar:
        st.markdown('<div class="side-label">Command terminal</div>', unsafe_allow_html=True)
        with st.form("term_form", clear_on_submit=True):
            raw = st.text_input(
                "command",
                placeholder="",
                label_visibility="collapsed",
            )
            run = st.form_submit_button("Run")

    if run and raw.strip():
        if raw.strip().lower() == "clear":
            st.session_state.term_log = []
        else:
            output = run_command(raw, cls, reader)
            log = st.session_state.get("term_log", [])
            log.insert(0, (raw.strip(), output))
            st.session_state.term_log = log[:8]


def render_terminal_log():
    """Terminal output panel on the dashboard."""
    log = st.session_state.get("term_log", [])
    if log:
        body = "".join(
            '<div class="tx-term-cmd"><span>$</span>' + _esc(cmd) + '</div>'
            '<div class="tx-term-out">'
            + "".join(f"<div>{_esc(line) or '&nbsp;'}</div>" for line in out.split("\n"))
            + '</div>'
            for cmd, out in log
        )
    else:
        body = '<div class="tx-term-out">Type "help" in the sidebar command box.</div>'

    st.markdown(
        '<div class="tx-card"><div class="tx-card-title">Terminal</div>'
        f'<div class="tx-term">{body}</div></div>',
        unsafe_allow_html=True,
    )
