"""
ui/views.py
Teacher pages opened from the sidebar menu. Live attendance stays in app.py.
"""

import html
import math
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from database.db import query_all, query_one
from database.schedule import list_schedule, schedule_text
from services.attendance_service import get_roster, roster_csv
from ui.roster_photos import student_cell

PAGES = [
    "Live attendance",
    "Dashboard",
    "Class roster",
    "Attendance records",
    "Reports and analytics",
    "Class settings",
]

RANGES = {"Last 7 days": 7, "Last 30 days": 30, "All time": None}
STATUS_ORDER = {"PRESENT": 0, "LATE": 1, "ABSENT": 2}


def esc(value) -> str:
    return html.escape(str(value or ""))


def status_badge(status: str) -> str:
    kind = {"PRESENT": "present", "LATE": "late", "ABSENT": "absent"}.get(status, "info")
    return f'<span class="badge badge-{kind}">{esc(status)}</span>'


def counts(rows: list) -> dict:
    total = len(rows)
    present = sum(1 for r in rows if r["Status"] == "PRESENT")
    late = sum(1 for r in rows if r["Status"] == "LATE")
    absent = total - present - late
    rate = round((present + late) * 100 / total) if total else 0
    return {"total": total, "present": present, "late": late, "absent": absent, "rate": rate}


def enrolled_count(class_id: int) -> int:
    row = query_one(
        "SELECT COUNT(*) AS n FROM students s "
        "JOIN class_offerings c ON c.section_id = s.section_id WHERE c.id = ?",
        (class_id,),
    )
    return row["n"] if row else 0


def share(part: int, total: int) -> str:
    return f"{round(part * 100 / total)}% of class" if total else "No students"


def stat_card(label: str, value, tone: str, foot: str) -> str:
    return (
        f'<div class="tx-stat tx-tone-{tone}">'
        f'<div class="tx-stat-value">{value}</div>'
        f'<div class="tx-stat-label">{esc(label)}</div>'
        f'<div class="tx-stat-foot">{esc(foot)}</div>'
        '</div>'
    )


def ring_svg(pct: int) -> str:
    r = 72
    circumference = 2 * math.pi * r
    offset = circumference * (1 - pct / 100)
    return (
        '<div class="tx-ring-wrap">'
        '<svg class="tx-ring-svg" viewBox="0 0 180 180">'
        '<defs><linearGradient id="txRingGradV" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0%" stop-color="#22c55e"/>'
        '<stop offset="100%" stop-color="#6366f1"/>'
        '</linearGradient></defs>'
        f'<circle class="track" cx="90" cy="90" r="{r}" fill="none" stroke-width="12"/>'
        f'<circle class="bar" cx="90" cy="90" r="{r}" fill="none" '
        'stroke="url(#txRingGradV)" stroke-width="12" stroke-linecap="round" '
        f'stroke-dasharray="{circumference:.2f}" stroke-dashoffset="{offset:.2f}"/>'
        '</svg>'
        '<div class="tx-ring-center">'
        f'<div class="tx-ring-value">{pct}%</div>'
        '<div class="tx-ring-label">present or late</div>'
        '</div></div>'
    )


def page_header(title: str, cls: dict, chip: str) -> None:
    st.markdown(
        '<div class="tx-hero"><div class="tx-hero-glow"></div><div class="tx-hero-body">'
        f'<div class="tx-eyebrow">{esc(cls["section"])} · {esc(cls["subject"])}</div>'
        f'<h1 class="tx-greeting">{esc(title)}</h1>'
        f'<div class="tx-chips"><span class="tx-chip">{esc(chip)}</span></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


def roster_table(rows: list) -> None:
    if not rows:
        st.markdown('<div class="tx-empty">No students match these filters.</div>', unsafe_allow_html=True)
        return
    body = "".join(
        "<tr>"
        f'<td class="mono">{esc(r["Student No."])}</td>'
        f'<td>{student_cell(r["Student No."], r["Name"])}</td>'
        f'<td>{status_badge(r["Status"])}</td>'
        f'<td class="mono">{esc(r["Time In"])}</td>'
        "</tr>"
        for r in rows
    )
    st.markdown(
        '<div class="tx-card" style="padding:0.6rem"><div class="table-wrap"><table class="roster">'
        '<thead><tr><th>Student No.</th><th>Name</th><th>Status</th><th>Time In</th></tr></thead>'
        f'<tbody>{body}</tbody></table></div></div>',
        unsafe_allow_html=True,
    )


def page_dashboard(cls: dict) -> None:
    page_header("Dashboard", cls, cls["teacher_name"])
    c = counts(get_roster(cls["id"]))
    st.markdown(
        '<div class="tx-stats">'
        + stat_card("Total students", c["total"], "total", "Enrolled in section")
        + stat_card("Present today", c["present"], "ok", share(c["present"], c["total"]))
        + stat_card("Late today", c["late"], "late", share(c["late"], c["total"]))
        + stat_card("Absent today", c["absent"], "bad", share(c["absent"], c["total"]))
        + '</div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.6, 1])
    with left:
        st.markdown(
            '<div class="tx-card tx-class-card"><div class="tx-card-title">Class information</div>'
            '<div class="tx-info-grid">'
            f'<div><span>Teacher</span><b>{esc(cls["teacher_name"])}</b></div>'
            f'<div><span>Section</span><b>{esc(cls["section"])}</b></div>'
            f'<div><span>Subject</span><b>{esc(cls["subject"])}</b></div>'
            f'<div><span>Schedule</span><b>{esc(schedule_text(cls["id"]))}</b></div>'
            f'<div><span>Enrolled</span><b>{enrolled_count(cls["id"])}</b></div>'
            f'<div><span>Date</span><b>{date.today():%A, %B %d, %Y}</b></div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            '<div class="tx-card tx-ring-card"><div class="tx-card-title">Attendance rate</div>'
            f'{ring_svg(c["rate"])}</div>',
            unsafe_allow_html=True,
        )


def page_roster(cls: dict) -> None:
    page_header("Class roster", cls, f"{enrolled_count(cls['id'])} enrolled")
    f1, f2, f3 = st.columns([2, 1.2, 1.2])
    with f1:
        search = st.text_input(
            "Search", key="ros_search", label_visibility="collapsed",
            placeholder="Search by name or student number",
        )
    with f2:
        status = st.selectbox(
            "Status", ["All", "PRESENT", "LATE", "ABSENT"], key="ros_status",
            label_visibility="collapsed",
        )
    with f3:
        sort_by = st.selectbox(
            "Sort by", ["Status", "Name", "Student No.", "Time In"], key="ros_sort",
            label_visibility="collapsed",
        )

    rows = get_roster(cls["id"])
    if status != "All":
        rows = [r for r in rows if r["Status"] == status]
    q = search.strip().lower()
    if q:
        rows = [r for r in rows if q in r["Name"].lower() or q in r["Student No."].lower()]

    if sort_by == "Name":
        rows.sort(key=lambda r: r["Name"])
    elif sort_by == "Student No.":
        rows.sort(key=lambda r: r["Student No."])
    elif sort_by == "Time In":
        rows.sort(key=lambda r: (r["Time In"] == "", r["Time In"]))
    else:
        rows.sort(key=lambda r: (STATUS_ORDER.get(r["Status"], 3), r["Name"]))

    st.markdown(f'<div class="tx-roster-meta">Showing {len(rows)} students</div>', unsafe_allow_html=True)
    roster_table(rows)

    filename = f"{cls['section']}_{cls['subject']}_{date.today().isoformat()}.csv".replace(" ", "_")
    st.download_button(
        label="Download today's roster (CSV)",
        data=roster_csv(cls["id"]).encode("utf-8-sig"),
        file_name=filename,
        mime="text/csv",
    )


def day_records(class_id: int, day: str) -> list:
    rows = query_all(
        """
        SELECT s.student_number, s.full_name,
               COALESCE(a.status, 'ABSENT') AS status, a.time_in
        FROM class_offerings c
        JOIN students s ON s.section_id = c.section_id
        LEFT JOIN attendance a
               ON a.id = (SELECT MIN(x.id) FROM attendance x
                          WHERE x.student_id = s.id
                            AND x.class_offering_id = c.id
                            AND x.attendance_date = ?)
        WHERE c.id = ?
        ORDER BY s.full_name
        """,
        (day, class_id),
    )
    return [
        {
            "Student No.": r["student_number"],
            "Name": r["full_name"],
            "Status": r["status"],
            "Time In": r["time_in"] or "",
        }
        for r in rows
    ]


def page_records(cls: dict) -> None:
    page_header("Attendance records", cls, "Pick a date")
    chosen = st.date_input("Date", value=date.today(), key="rec_date")
    if chosen > date.today():
        st.info("This date hasn't happened yet.")
        return

    rows = day_records(cls["id"], chosen.isoformat())
    c = counts(rows)
    st.markdown(
        '<div class="tx-stats">'
        + stat_card("Total students", c["total"], "total", "Enrolled in section")
        + stat_card("Present", c["present"], "ok", share(c["present"], c["total"]))
        + stat_card("Late", c["late"], "late", share(c["late"], c["total"]))
        + stat_card("Absent", c["absent"], "bad", share(c["absent"], c["total"]))
        + '</div>',
        unsafe_allow_html=True,
    )
    rows.sort(key=lambda r: (STATUS_ORDER.get(r["Status"], 3), r["Name"]))
    roster_table(rows)


PLOT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#cbd5e1", size=12),
    margin=dict(l=8, r=8, t=28, b=8),
    hoverlabel=dict(bgcolor="#131a2e", bordercolor="#242f4d", font=dict(color="#e8edf8")),
    xaxis=dict(gridcolor="rgba(36,47,77,0.5)", linecolor="rgba(36,47,77,0.8)", zerolinecolor="rgba(36,47,77,0.5)"),
    yaxis=dict(gridcolor="rgba(36,47,77,0.5)", linecolor="rgba(36,47,77,0.8)", zerolinecolor="rgba(36,47,77,0.5)"),
)
LEGEND = dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(color="#cbd5e1"))


def daily_bar_chart(df) -> None:
    fig = go.Figure()
    for col, color in (("Present", "#22c55e"), ("Late", "#f59e0b"), ("Absent", "#ef4444")):
        fig.add_bar(x=df["Date"], y=df[col], name=col, marker_color=color)
    fig.update_layout(barmode="stack", bargap=0.45, height=320, legend=LEGEND, **PLOT_BASE)
    st.plotly_chart(fig, config={"displayModeBar": False})


def rate_line_chart(df) -> None:
    fig = go.Figure()
    fig.add_scatter(
        x=df["Date"], y=df["Rate"], mode="lines+markers", name="Attendance",
        line=dict(color="#6366f1", width=3, shape="spline"),
        marker=dict(size=9, color="#a5b4fc", line=dict(color="#6366f1", width=2)),
        fill="tozeroy", fillcolor="rgba(99,102,241,0.15)",
        hovertemplate="%{x}<br>%{y:.0f}%<extra></extra>",
    )
    fig.update_yaxes(range=[0, 100], ticksuffix="%")
    fig.update_layout(height=280, showlegend=False, **PLOT_BASE)
    st.plotly_chart(fig, config={"displayModeBar": False})


def html_table(rows: list, columns: list) -> None:
    head = "".join(f"<th>{esc(c)}</th>" for c in columns)
    body = "".join(
        "<tr>"
        + "".join(
            f'<td class="mono">{esc(r[c])}</td>' if c == "Student No." else f"<td>{esc(r[c])}</td>"
            for c in columns
        )
        + "</tr>"
        for r in rows
    )
    st.markdown(
        '<div class="tx-card" style="padding:0.6rem"><div class="table-wrap"><table class="roster">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></div>",
        unsafe_allow_html=True,
    )


def page_reports(cls: dict) -> None:
    page_header("Reports and analytics", cls, "From the attendance database")
    choice = st.radio("Range", list(RANGES), horizontal=True, key="rep_range")
    days = RANGES[choice]
    since = (date.today() - timedelta(days=days)).isoformat() if days else "0000-01-01"
    enrolled = enrolled_count(cls["id"])

    daily = query_all(
        """
        SELECT attendance_date AS d,
               SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) AS present,
               SUM(CASE WHEN status = 'LATE' THEN 1 ELSE 0 END) AS late
        FROM attendance
        WHERE class_offering_id = ? AND attendance_date >= ?
        GROUP BY attendance_date
        ORDER BY attendance_date
        """,
        (cls["id"], since),
    )
    if not daily:
        st.info("No attendance recorded in this range yet.")
        return

    df = pd.DataFrame(
        [
            {
                "Date": r["d"],
                "Present": r["present"],
                "Late": r["late"],
                "Absent": max(enrolled - r["present"] - r["late"], 0),
            }
            for r in daily
        ]
    )
    df["Rate"] = (df["Present"] + df["Late"]) * 100 / enrolled if enrolled else 0

    total_late = int(df["Late"].sum())
    attended = int((df["Present"] + df["Late"]).sum())
    late_share = round(total_late * 100 / attended) if attended else 0
    avg_rate = round(float(df["Rate"].mean()))
    st.markdown(
        '<div class="tx-stats">'
        + stat_card("Class days", len(df), "total", "With records")
        + stat_card("Average attendance", f"{avg_rate}%", "ok", "Present or late")
        + stat_card("Late arrivals", total_late, "late", f"{late_share}% of attendance")
        + stat_card("Absences", int(df["Absent"].sum()), "bad", "Across all class days")
        + '</div>',
        unsafe_allow_html=True,
    )

    total_days = query_one(
        "SELECT COUNT(DISTINCT attendance_date) AS n FROM attendance "
        "WHERE class_offering_id = ? AND attendance_date >= ?",
        (cls["id"], since),
    )["n"]
    students = query_all(
        """
        SELECT s.student_number, s.full_name,
               COUNT(DISTINCT CASE WHEN a.status IN ('PRESENT', 'LATE')
                                   THEN a.attendance_date END) AS attended
        FROM class_offerings c
        JOIN students s ON s.section_id = c.section_id
        LEFT JOIN attendance a
               ON a.student_id = s.id
              AND a.class_offering_id = c.id
              AND a.attendance_date >= ?
        WHERE c.id = ?
        GROUP BY s.id
        """,
        (since, cls["id"]),
    )
    absent_rows = []
    for r in students:
        missed = total_days - r["attended"]
        if missed > 0:
            absent_rows.append(
                {
                    "Student No.": r["student_number"],
                    "Name": r["full_name"],
                    "Days absent": missed,
                    "Attendance": f'{round(r["attended"] * 100 / total_days)}%',
                }
            )
    absent_rows.sort(key=lambda r: r["Days absent"], reverse=True)

    st.markdown('<div class="tx-section-title">Frequently absent</div>', unsafe_allow_html=True)
    if absent_rows:
        html_table(
            absent_rows[:10],
            ["Student No.", "Name", "Days absent", "Attendance"],
        )
    else:
        st.markdown('<div class="tx-empty">No absences in this range.</div>', unsafe_allow_html=True)

def page_settings(cls: dict) -> None:
    page_header("Class settings", cls, "Read only")
    st.markdown(
        '<div class="tx-card tx-class-card"><div class="tx-card-title">Class details</div>'
        '<div class="tx-info-grid">'
        f'<div><span>Teacher</span><b>{esc(cls["teacher_name"])}</b></div>'
        f'<div><span>Section</span><b>{esc(cls["section"])}</b></div>'
        f'<div><span>Subject</span><b>{esc(cls["subject"])}</b></div>'
        f'<div><span>Default time</span><b>{esc(cls.get("start_time"))} – {esc(cls.get("end_time"))}</b></div>'
        f'<div><span>Class code</span><b class="mono">{esc(cls.get("access_code"))}</b></div>'
        f'<div><span>Today</span><b>{esc(schedule_text(cls["id"]))}</b></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="tx-section-title">Weekly schedule</div>', unsafe_allow_html=True)
    rows = [
        {"Day": label, "Time": text, "Source": "Custom" if custom else "Default"}
        for label, text, custom in list_schedule(cls["id"])
    ]
    html_table(rows, ["Day", "Time", "Source"])
    st.caption("Schedule changes are made by the administrator. Use Reschedule on Live attendance for a single date.")


def render_page(page: str, cls: dict) -> None:
    if page == "Dashboard":
        page_dashboard(cls)
    elif page == "Class roster":
        page_roster(cls)
    elif page == "Attendance records":
        page_records(cls)
    elif page == "Reports and analytics":
        page_reports(cls)
    elif page == "Class settings":
        page_settings(cls)