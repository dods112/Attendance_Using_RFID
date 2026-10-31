"""
ui/sidebar.py
Sidebar navigation. Each menu item is a real Streamlit button.
Clicking one switches the page, and the active item gets a highlight.
"""

import html

import streamlit as st

from config import APP_TITLE

NAV_ITEMS = [
    ("Live attendance", "Live Attendance", "nav_live"),
    ("Dashboard", "Dashboard", "nav_dashboard"),
    ("Class roster", "Class Roster", "nav_roster"),
    ("Attendance records", "Attendance Records", "nav_records"),
    ("Reports and analytics", "Reports & Analytics", "nav_reports"),
    ("Class settings", "Class Settings", "nav_settings"),
]

ACTIVE_STYLE = """
<style>
section[data-testid="stSidebar"] .st-key-{key} button,
section[data-testid="stSidebar"] .st-key-{key} button:hover {
  background: rgba(99, 102, 241, 0.22) !important;
  border-color: rgba(129, 140, 248, 0.6) !important;
  color: #ffffff !important;
  font-weight: 600 !important;
  box-shadow: 0 0 18px rgba(99, 102, 241, 0.28) !important;
}
section[data-testid="stSidebar"] .st-key-{key} button::before {
  background-color: #a5b4fc !important;
}
</style>
"""

BRAND_ICON = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
    'stroke-linecap="round" stroke-linejoin="round" width="22" height="22">'
    '<rect x="5" y="4" width="14" height="17" rx="2"/>'
    '<path d="M9 4V3h6v1"/><path d="M9 11h6M9 15h4"/></svg>'
)


def _esc(value) -> str:
    return html.escape(str(value or ""))


def _set_page(page: str) -> None:
    st.session_state.nav_page = page


def _initials(name: str) -> str:
    titles = {"sir", "ma'am", "maam", "mr", "ms", "mrs"}
    words = [w for w in name.split() if w.lower().strip(",") not in titles]
    return "".join(w[0] for w in words[:2]).upper() or "?"


def show_sidebar(reader) -> str:
    """Draws the sidebar and returns the page the teacher picked."""
    if "nav_page" not in st.session_state:
        st.session_state.nav_page = "Live attendance"
    cls = st.session_state.get("current_class")

    with st.sidebar:
        st.markdown(
            '<div class="side-brand">'
            f'<div class="side-logo">{BRAND_ICON}</div>'
            '<div>'
            f'<div class="side-name">{_esc(APP_TITLE)}</div>'
            '<div class="side-tag">Attendance · Heisenberg</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )

        if cls is None:
            st.markdown('<div class="nav-label">Sign in</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="side-card"><div class="side-card-sub">'
                'Enter your class code to open your class.</div></div>',
                unsafe_allow_html=True,
            )
            return "Live attendance"

        active = st.session_state.nav_page
        active_key = next(key for page, _, key in NAV_ITEMS if page == active)
        st.markdown(ACTIVE_STYLE.replace("{key}", active_key), unsafe_allow_html=True)

        st.markdown('<div class="nav-label">Menu</div>', unsafe_allow_html=True)
        for page, label, key in NAV_ITEMS:
            st.button(label, key=key, width="stretch", on_click=_set_page, args=(page,))

        st.markdown('<div class="nav-label">Account</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="side-profile">'
            f'<div class="side-avatar">{_esc(_initials(cls["teacher_name"]))}</div>'
            '<div>'
            f'<div class="side-profile-name">{_esc(cls["teacher_name"])}</div>'
            f'<div class="side-profile-role">Teacher · {_esc(cls["section"])}</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Log out", key="sb_logout", width="stretch"):
            reader.active_class_id = None
            st.session_state.current_class = None
            st.session_state.nav_page = "Live attendance"
            st.rerun()

    return st.session_state.nav_page