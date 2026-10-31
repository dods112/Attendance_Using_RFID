"""
ui/demo.py
Simulated card taps for demos without the Arduino.
Each tap goes through the same code path as a real scan, so the feed,
roster, popup, and database all update exactly as they do for a real card.
Shown only when DEMO_MODE is on.
"""

import streamlit as st

from database.db import query_all

UNKNOWN_UID = "00000000"


def _students(class_id: int) -> list:
    return query_all(
        """
        SELECT s.rfid_uid, s.full_name, s.student_number
        FROM class_offerings c
        JOIN students s ON s.section_id = c.section_id
        WHERE c.id = ? AND s.rfid_uid IS NOT NULL
        ORDER BY s.full_name
        """,
        (class_id,),
    )


def demo_controls(reader, cls: dict, enabled: bool) -> None:
    if not enabled:
        return

    students = _students(cls["id"])
    with st.expander("Demo: simulate card taps", expanded=True):
        if not students:
            st.caption("No students with cards in this database yet.")
            return

        labels = [f'{s["full_name"]} ({s["student_number"]})' for s in students]
        choice = st.selectbox(
            "Student",
            range(len(labels)),
            format_func=lambda i: labels[i],
            key="demo_pick",
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Tap student card", key="demo_tap", width="stretch"):
                reader.simulate_scan(students[choice]["rfid_uid"])
        with col2:
            if st.button("Tap unknown card", key="demo_unknown", width="stretch"):
                reader.simulate_scan(UNKNOWN_UID)