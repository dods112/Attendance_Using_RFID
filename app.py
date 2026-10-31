"""
app.py
Teacher dashboard: class-code login, live attendance, roster, and recent scans.
Run with: python -m streamlit run app.py
"""
import base64
import html
import math
from datetime import date, datetime, time, timedelta

import streamlit as st

from config import (
    APP_TITLE, APP_ICON, CSS_PATH, BASE_DIR,
    SERIAL_PORT, BAUD_RATE, SERIAL_RECONNECT_SECONDS,
)
from database.db import init_db, query_one
from database.classes import get_class_by_code
from database.schedule import (
    schedule_text,
    set_date_override,
    restore_default_for_date,
    move_class,
)
from services.attendance_service import get_roster, roster_csv
from services.serial_service import SerialReader
from ui.views import PAGES, render_page
from ui.sidebar import show_sidebar
from ui.terminal import show_terminal_input, render_terminal_log


st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide", initial_sidebar_state="expanded")

init_db()

if CSS_PATH.exists():
    st.markdown(
        f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )


@st.cache_resource
def get_reader() -> SerialReader:
    """Start the Arduino reader once for the whole server, not once per page load."""
    reader = SerialReader(SERIAL_PORT, BAUD_RATE, SERIAL_RECONNECT_SECONDS)
    reader.start()
    return reader


reader = get_reader()

if "current_class" not in st.session_state:
    st.session_state.current_class = None

STATUS_ORDER = {"PRESENT": 0, "LATE": 1, "ABSENT": 2}

RESULT_TONE = {
    "PRESENT": "ok",
    "LATE": "late",
    "ALREADY RECORDED": "info",
    "OUTSIDE CLASS TIME": "warn",
    "WRONG CLASS": "bad",
    "UNREGISTERED": "bad",
    "NO CLASS ACTIVE": "bad",
}

# Line icons (Lucide-style). Drawn in currentColor, so they follow the tone color.
_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round">{}</svg>'
)
ICONS = {
    "clipboard": _SVG.format(
        '<rect x="5" y="4" width="14" height="17" rx="2"/>'
        '<path d="M9 4V3h6v1"/><path d="M9 11h6M9 15h4"/>'
    ),
    "users": _SVG.format(
        '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/>'
        '<circle cx="9" cy="7" r="4"/>'
        '<path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>'
    ),
    "check": _SVG.format(
        '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>'
    ),
    "clock": _SVG.format(
        '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>'
    ),
    "x": _SVG.format(
        '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>'
    ),
    "book": _SVG.format(
        '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15z"/>'
        '<path d="M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5"/>'
    ),
    "calendar": _SVG.format(
        '<rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<path d="M16 2v4M8 2v4M3 10h18"/>'
    ),
    "layers": _SVG.format(
        '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>'
    ),
}


# ---------- Helpers ----------

def esc(value) -> str:
    """Escape text so names like O'Brien can't break the HTML."""
    return html.escape(str(value or ""))


def icon(name: str) -> str:
    return ICONS.get(name, "")


def status_badge(status: str) -> str:
    kind = {"PRESENT": "present", "LATE": "late", "ABSENT": "absent"}.get(status, "info")
    return f'<span class="badge badge-{kind}">{esc(status)}</span>'


def is_fresh(stamp: str, seconds: int = 4) -> bool:
    """True if an HH:MM:SS timestamp happened within the last few seconds."""
    try:
        t = datetime.strptime(stamp, "%H:%M:%S").time()
    except (ValueError, TypeError):
        return False
    now = datetime.now()
    delta = (now - datetime.combine(now.date(), t)).total_seconds()
    return 0 <= delta <= seconds


def student_for_card(uid: str):
    if not uid:
        return None
    return query_one(
        "SELECT student_number, full_name FROM students WHERE rfid_uid = ?", (uid,)
    )


def enrolled_count(class_id: int) -> int:
    row = query_one(
        "SELECT COUNT(*) AS n FROM students s "
        "JOIN class_offerings c ON c.section_id = s.section_id WHERE c.id = ?",
        (class_id,),
    )
    return row["n"] if row else 0


def snapshot(class_id: int):
    """Roster plus counts for the active class, all read from SQLite."""
    roster = get_roster(class_id)
    total = len(roster)
    present = sum(1 for r in roster if r["Status"] == "PRESENT")
    late = sum(1 for r in roster if r["Status"] == "LATE")
    absent = total - present - late
    pct = round((present + late) * 100 / total) if total else 0
    return roster, {
        "total": total, "present": present, "late": late,
        "absent": absent, "pct": pct,
    }


def ring_svg(pct: int) -> str:
    """Attendance ring drawn as SVG. The arc length follows the percentage."""
    r = 72
    circumference = 2 * math.pi * r
    offset = circumference * (1 - pct / 100)
    return (
        '<div class="tx-ring-wrap">'
        '<svg class="tx-ring-svg" viewBox="0 0 180 180">'
        '<defs><linearGradient id="txRingGrad" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#22c55e"/>'
        '<stop offset="100%" stop-color="#6366f1"/>'
        '</linearGradient></defs>'
        f'<circle class="track" cx="90" cy="90" r="{r}" fill="none" stroke-width="12"/>'
        f'<circle class="bar" cx="90" cy="90" r="{r}" fill="none" '
        'stroke="url(#txRingGrad)" stroke-width="12" stroke-linecap="round" '
        f'stroke-dasharray="{circumference:.2f}" stroke-dashoffset="{offset:.2f}"/>'
        '</svg>'
        '<div class="tx-ring-center">'
        f'<div class="tx-ring-value">{pct}%</div>'
        '<div class="tx-ring-label">present or late</div>'
        '</div></div>'
    )


# ---------- Sidebar ----------

# ---------- Login ----------

def show_login():
    _, middle, _ = st.columns([1, 1.1, 1])
    with middle:
        st.markdown(
            '<div class="login-hero">'
            f'<div class="login-icon">{icon("clipboard")}</div>'
            f'<div class="login-title">{esc(APP_TITLE)}</div>'
            '<div class="login-sub">Enter your class code to start taking attendance</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            code = st.text_input(
                "Class code",
                placeholder="e.g. HEI-CHEM1-3QU5",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Enter class")

        if submitted:
            found = get_class_by_code(code)
            if found is None:
                st.error("Invalid class code. Please check and try again.")
            else:
                st.session_state.current_class = dict(found)
                st.rerun()


# ---------- Live fragments (refresh every 2 seconds) ----------

@st.fragment(run_every=2)
def attendance_ring(class_id: int):
    _, s = snapshot(class_id)
    st.markdown(
        '<div class="tx-card tx-ring-card">'
        '<div class="tx-card-title">Attendance rate</div>'
        f'{ring_svg(s["pct"])}'
        '</div>',
        unsafe_allow_html=True,
    )


@st.fragment(run_every=2)
def stats_panel(class_id: int):
    _, s = snapshot(class_id)
    total = s["total"] or 1

    def share(n: int) -> str:
        return f"{round(n * 100 / total)}% of class" if s["total"] else "No students"

    items = [
        ("Total students", s["total"], "total", "users", "Enrolled in section"),
        ("Present today", s["present"], "ok", "check", share(s["present"])),
        ("Late today", s["late"], "late", "clock", share(s["late"])),
        ("Absent today", s["absent"], "bad", "x", share(s["absent"])),
    ]
    cards = "".join(
        f'<div class="tx-stat tx-tone-{tone}">'
        '<div class="tx-stat-top">'
        f'<span class="tx-icon">{icon(ico)}</span>'
        '</div>'
        f'<div class="tx-stat-value">{value}</div>'
        f'<div class="tx-stat-label">{label}</div>'
        f'<div class="tx-stat-foot">{foot}</div>'
        '</div>'
        for label, value, tone, ico, foot in items
    )
    st.markdown(f'<div class="tx-stats">{cards}</div>', unsafe_allow_html=True)


PHOTO_DIR = BASE_DIR / "assets" / "students"
PHOTO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def student_photo_src(student_number: str):
    """Return the student's photo as a data URI, or None if no photo file exists."""
    for ext, mime in PHOTO_MIME.items():
        path = PHOTO_DIR / f"{student_number}{ext}"
        if path.exists():
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"
    return None


def initials(full_name: str) -> str:
    """'PARA, ALDE' -> 'PA'."""
    surname, _, given = full_name.partition(",")
    given_words = given.split()
    first = given_words[0] if given_words else ""
    return (surname.strip()[:1] + first[:1]).upper() or "?"


def avatar_html(student, tone: str) -> str:
    """Photo if available, otherwise initials. The tone class colors the ring."""
    if student is None:
        return f'<div class="tx-avatar tx-avatar-initials tx-tone-{tone}">?</div>'
    src = student_photo_src(student["student_number"])
    if src:
        return f'<img class="tx-avatar tx-tone-{tone}" src="{src}" alt="">'
    return (
        f'<div class="tx-avatar tx-avatar-initials tx-tone-{tone}">'
        f'{esc(initials(student["full_name"]))}</div>'
    )


@st.fragment(run_every=2)
def live_panel(cls: dict):
    events = list(reader.events)
    latest = events[0] if events else None

    if reader.connected:
        device = (
            '<div class="tx-device">'
            '<span class="tx-dot tx-dot-on"></span>'
            '<div><div class="tx-device-title">Arduino connected</div>'
            f'<div class="tx-device-sub">{esc(SERIAL_PORT)} · {BAUD_RATE} baud · RFID ready</div></div>'
            '</div>'
        )
        scanner = (
            '<div class="tx-scanner"><span></span><span></span>'
            '<div class="tx-scanner-core"></div></div>'
        )
    else:
        device = (
            '<div class="tx-device">'
            '<span class="tx-dot tx-dot-off"></span>'
            '<div><div class="tx-device-title">Arduino offline</div>'
            f'<div class="tx-device-sub">Retrying {esc(SERIAL_PORT)}… {esc(reader.last_error)}</div></div>'
            '</div>'
        )
        scanner = (
            '<div class="tx-scanner tx-scanner-off"><span></span><span></span>'
            '<div class="tx-scanner-core"></div></div>'
        )

    if latest is None:
        body = '<div class="tx-latest-empty">Waiting for a card scan…</div>'
    else:
        tone = RESULT_TONE.get(latest["Result"], "info")
        student = student_for_card(latest["Card"])
        number = esc(student["student_number"]) if student else "Not registered"
        name = esc(latest["Name"]) or "Unregistered card"
        recorded = latest["Result"] in ("PRESENT", "LATE")
        fresh = is_fresh(latest["Time"])

        banner = (
            '<div class="tx-success">Attendance successfully recorded!</div>'
            if recorded and fresh else ""
        )
        fresh_class = " tx-fresh" if fresh else ""
        body = (
            banner
            + f'<div class="tx-latest tx-latest-wrap{fresh_class}">'
            + avatar_html(student, tone)
            + '<div class="tx-latest-text">'
            + f'<div class="tx-latest-name">{name}</div>'
            + f'<div class="tx-latest-meta">Student No. {number} · {esc(latest["Time"])}</div>'
            + f'<div class="tx-latest-row"><span class="tx-badge tx-badge-{tone}">'
            + f'{esc(latest["Result"])}</span></div>'
            + '</div></div>'
        )

    st.markdown(
        '<div class="tx-card">'
        '<div class="tx-card-title">Live RFID monitoring</div>'
        f'<div class="tx-device-row">{device}{scanner}</div>'
        f'{body}'
        '</div>',
        unsafe_allow_html=True,
    )


@st.fragment(run_every=2)
def feed_panel(subject: str):
    events = list(reader.events)[:12]
    if not events:
        items = '<div class="tx-empty">No scans yet this session.</div>'
    else:
        parts = []
        for i, e in enumerate(events):
            tone = RESULT_TONE.get(e["Result"], "info")
            student = student_for_card(e["Card"])
            number = esc(student["student_number"]) if student else "Not registered"
            name = esc(e["Name"]) or f'Card {esc(e["Card"])}'
            fresh = " tx-feed-fresh" if i == 0 and is_fresh(e["Time"]) else ""
            parts.append(
                f'<div class="tx-feed-item tx-tone-{tone}{fresh}">'
                f'<div class="tx-feed-time">{esc(e["Time"])}</div>'
                '<div class="tx-feed-main">'
                f'<div class="tx-feed-name">{name}</div>'
                f'<div class="tx-feed-sub">{number} · {esc(subject)}</div>'
                '</div>'
                f'<span class="tx-badge tx-badge-{tone}">{esc(e["Result"])}</span>'
                '</div>'
            )
        items = "".join(parts)

    st.markdown(
        '<div class="tx-card"><div class="tx-card-title">Recent scans</div>'
        f'{items}</div>',
        unsafe_allow_html=True,
    )


@st.fragment(run_every=2)
def roster_panel(class_id: int):
    """Reads the filter widgets' saved values, so it works without re-running the page."""
    search = st.session_state.get("roster_search", "").strip().lower()
    status_filter = st.session_state.get("roster_status", "All")
    sort_by = st.session_state.get("roster_sort", "Status")

    roster = get_roster(class_id)
    rows = []
    for r in roster:
        if status_filter != "All" and r["Status"] != status_filter:
            continue
        if search and search not in r["Name"].lower() and search not in str(r["Student No."]).lower():
            continue
        rows.append(r)

    if sort_by == "Name":
        rows.sort(key=lambda r: r["Name"])
    elif sort_by == "Student No.":
        rows.sort(key=lambda r: r["Student No."])
    elif sort_by == "Time In":
        rows.sort(key=lambda r: (r["Time In"] == "", r["Time In"]))
    else:
        rows.sort(key=lambda r: (STATUS_ORDER.get(r["Status"], 3), r["Name"]))

    st.markdown(
        f'<div class="tx-roster-meta">Showing {len(rows)} of {len(roster)} students</div>',
        unsafe_allow_html=True,
    )

    if not rows:
        st.markdown('<div class="tx-empty">No students match these filters.</div>', unsafe_allow_html=True)
        return

    body = "".join(
        "<tr>"
        f'<td class="mono">{esc(r["Student No."])}</td>'
        f'<td>{esc(r["Name"])}</td>'
        f'<td>{status_badge(r["Status"])}</td>'
        f'<td class="mono">{esc(r["Time In"])}</td>'
        "</tr>"
        for r in rows
    )
    st.markdown(
        '<div class="tx-card" style="padding:0.6rem">'
        '<div class="table-wrap"><table class="roster">'
        '<thead><tr><th>Student No.</th><th>Name</th><th>Status</th><th>Time In</th></tr></thead>'
        f'<tbody>{body}</tbody>'
        '</table></div></div>',
        unsafe_allow_html=True,
    )

RESCHEDULE_ACTIONS = [
    "Change time on this date",
    "Cancel class on this date",
    "Move class to another date",
    "Restore default for this date",
]


@st.dialog("Reschedule class")
def reschedule_dialog(cls: dict):
    st.caption(
        f'{cls["subject"]} · {cls["section"]}. Changes apply only to the date you pick. '
        "The weekly schedule stays the same."
    )

    action = st.radio("What do you want to do?", RESCHEDULE_ACTIONS, key="rs_action")
    picked = st.date_input("Date", value=date.today(), key="rs_date")

    target = None
    if action == "Move class to another date":
        target = st.date_input("Move to", value=picked + timedelta(days=1), key="rs_target")

    start_txt = end_txt = None
    if action in ("Change time on this date", "Move class to another date"):
        c1, c2 = st.columns(2)
        with c1:
            start_t = st.time_input("Start", value=time(12, 20), step=300, key="rs_start")
        with c2:
            end_t = st.time_input("End", value=time(13, 50), step=300, key="rs_end")
        start_txt = start_t.strftime("%H:%M")
        end_txt = end_t.strftime("%H:%M")

    if st.button("Save changes", type="primary", use_container_width=True):
        msg = None
        try:
            if action == "Change time on this date":
                set_date_override(cls["id"], picked, start_txt, end_txt)
                msg = f"{picked:%b %d}: class set to {start_txt} – {end_txt}."
            elif action == "Cancel class on this date":
                set_date_override(cls["id"], picked, None, None)
                msg = f"{picked:%b %d}: no class."
            elif action == "Move class to another date":
                move_class(cls["id"], picked, target, start_txt, end_txt)
                msg = (
                    f"Class moved from {picked:%b %d} to {target:%b %d}, "
                    f"{start_txt} – {end_txt}."
                )
            else:
                restore_default_for_date(cls["id"], picked)
                msg = f"{picked:%b %d}: default schedule restored."
        except ValueError as err:
            st.error(str(err))
        if msg:
            st.session_state.rs_flash = msg
            st.rerun()

# ---------- Teacher dashboard ----------

def show_welcome(cls: dict):
    reader.active_class_id = cls["id"]

    flash = st.session_state.pop("rs_flash", None)
    if flash:
        st.success(flash)

    total = enrolled_count(cls["id"])
    window = esc(schedule_text(cls["id"]))
    today = date.today().strftime("%A, %B %d, %Y")

    # Greeting banner
    st.markdown(
        '<div class="tx-hero"><div class="tx-hero-glow"></div><div class="tx-hero-body">'
        f'<div class="tx-eyebrow">Now monitoring · {esc(cls["section"])}</div>'
        f'<h1 class="tx-greeting">Welcome back, {esc(cls["teacher_name"])}!</h1>'
        '<div class="tx-chips">'
        f'<span class="tx-chip"><span class="tx-chip-icon">{icon("book")}</span>{esc(cls["subject"])}</span>'
        f'<span class="tx-chip"><span class="tx-chip-icon">{icon("clock")}</span>{window}</span>'
        f'<span class="tx-chip"><span class="tx-chip-icon">{icon("users")}</span>{total} enrolled</span>'
        '</div></div>'
        f'<div class="tx-hero-date">{today}</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Class information and attendance rate
    info_col, ring_col = st.columns([1.6, 1])
    with info_col:
        st.markdown(
            '<div class="tx-card tx-class-card">'
            '<div class="tx-card-title">Class information</div>'
            '<div class="tx-info-grid">'
            f'<div><span>Teacher</span><b>{esc(cls["teacher_name"])}</b></div>'
            f'<div><span>Section</span><b>{esc(cls["section"])}</b></div>'
            f'<div><span>Subject</span><b>{esc(cls["subject"])}</b></div>'
            f'<div><span>Schedule</span><b>{window}</b></div>'
            f'<div><span>Enrolled</span><b>{total}</b></div>'
            f'<div><span>Date</span><b>{today}</b></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    with ring_col:
        attendance_ring(cls["id"])

    stats_panel(cls["id"])

    live_col, feed_col = st.columns([1.2, 1])
    with live_col:
        live_panel(cls)
    with feed_col:
        feed_panel(cls["subject"])

    # Roster with filters
    st.markdown('<div class="tx-section-title">Class roster</div>', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([2, 1.2, 1.2])
    with f1:
        st.text_input(
            "Search", key="roster_search", label_visibility="collapsed",
            placeholder="Search by name or student number",
        )
    with f2:
        st.selectbox(
            "Status", ["All", "PRESENT", "LATE", "ABSENT"], key="roster_status",
            label_visibility="collapsed",
        )
    with f3:
        st.selectbox(
            "Sort by", ["Status", "Name", "Student No.", "Time In"], key="roster_sort",
            label_visibility="collapsed",
        )
    roster_panel(cls["id"])

    # Footer actions
    filename = f"{cls['section']}_{cls['subject']}_{date.today().isoformat()}.csv".replace(" ", "_")
    dl_col, rs_col, out_col, _ = st.columns([1.4, 1, 1, 2])
    with dl_col:
        st.download_button(
            label="Download today's roster (CSV)",
            data=roster_csv(cls["id"]).encode("utf-8-sig"),
            file_name=filename,
            mime="text/csv",
        )
    with rs_col:
        want_reschedule = st.button("Reschedule", use_container_width=True)
    with out_col:
        logout = st.button("Log out", use_container_width=True)

    if want_reschedule:
        reschedule_dialog(cls)

    if logout:
        reader.active_class_id = None
        st.session_state.current_class = None
        st.rerun()

# ---------- Routing (keep this block once, at the bottom) ----------

page = show_sidebar(reader)

if st.session_state.current_class is None:
    show_login()
else:
    cls = st.session_state.current_class
    reader.active_class_id = cls["id"]
    if page == "Live attendance":
        show_welcome(cls)
    else:
        render_page(page, cls)
