"""
app.py — Entry Point for Health-Self-Healing-Hermes
Architecture: Streamlit-based Multi-agent Orchestrator
"""

# --- SQLITE HACK (required for cloud/environment compatibility) ---
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import os
import time
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from core.config import APP_TITLE, APP_ICON, UI_CSS, PAGES
from core.session import init_session, add_log, get_logs, append_message
from core.db import load_synthetic_data, sync_from_hf, backup_to_hf
from core.gemini import get_active_model_label
from agents import AGENT_REGISTRY

# ---------------------------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown(UI_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# GLOBAL STICKY TITLE CSS
# ---------------------------------------------------------------------------
GLOBAL_STICKY_CSS = """
<style>
/* ── Hide Streamlit auto-nav + remove reserved gap ── */
[data-testid="stSidebarNav"] { display: none !important; }
[data-testid="stSidebarNavItems"] { display: none !important; }
[data-testid="stSidebarNavLink"] { display: none !important; }
section[data-testid="stSidebar"] nav { display: none !important; }
section[data-testid="stSidebar"] > div > div > div > ul { display: none !important; }
.st-emotion-cache-1rtdyuf { display: none !important; }
.st-emotion-cache-eczf2c { display: none !important; }
.st-emotion-cache-6tkfeg { display: none !important; }
[data-testid="stSidebarNav"] { animation: none !important; display: none !important; }

/* ── Remove the blank gap Streamlit reserves for the hidden nav ── */
section[data-testid="stSidebar"] > div:first-child {
    padding-top: 0rem !important;
}
section[data-testid="stSidebar"] > div > div:first-child {
    margin-top: 0rem !important;
    padding-top: 0.5rem !important;
}
div[data-testid="stSidebarContent"] {
    padding-top: 0.5rem !important;
}

/* ── Sticky chat title — persists through scroll ──────────────────────── */
.hdw-sticky-title {
    position: -webkit-sticky;
    position: sticky;
    top: 0;
    z-index: 9999;
    background: #0e0e1a;
    padding: 14px 0 10px 0;
    border-bottom: 1px solid #2a2a3d;
    margin-bottom: 14px;
}
.hdw-sticky-title span {
    color: #f5c842;
    font-family: 'Space Mono', monospace;
    font-size: 32px;
    font-weight: bold;
    letter-spacing: 0.04em;
}

/* ── Remove default Streamlit top padding ── */
.block-container {
    padding-top: 1rem !important;
}

/* ── Nav buttons in sidebar: styled like menu items ── */
div[data-testid="stSidebar"] div.stButton > button {
    font-family: 'Space Mono', monospace !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    letter-spacing: 0.05em !important;
    text-align: left !important;
    padding: 9px 14px !important;
    border-radius: 6px !important;
    border: 1px solid #2a2a3d !important;
    background: #0e0e1a !important;
    color: #aaaacc !important;
    margin-bottom: 3px !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
}
div[data-testid="stSidebar"] div.stButton > button:hover {
    background: #1a1a2e !important;
    color: #ffffff !important;
    border-color: #5a5a8a !important;
    transform: translateX(2px) !important;
}
div[data-testid="stSidebar"] div.stButton > button:active {
    background: #22223a !important;
    color: #f5c842 !important;
}
</style>
"""
st.markdown(GLOBAL_STICKY_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SYSTEM INITIALIZATION
# ---------------------------------------------------------------------------
init_session()
load_synthetic_data()

# ---------------------------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------------------------
def _get_agent_instance(entry):
    if isinstance(entry, type):
        return entry()
    return entry

def display_system_logs():
    logs = get_logs()
    if logs:
        st.code("\n".join(logs), language="bash")
    else:
        st.caption("System Status: Ready")

# ---------------------------------------------------------------------------
# SHARED NAV RENDERER — call this from any page to show the nav bar
# ---------------------------------------------------------------------------
PAGE_META = {
    "💬 Agent Chat":            {"color": "#f5c842", "glyph": "◎", "label": "Chat"},
    "📊 Health Risk Dashboard": {"color": "#3fb87b", "glyph": "◈", "label": "Dashboard"},
    "📄 EHR Summarizer":        {"color": "#5cc8f5", "glyph": "◑", "label": "EHR Summarizer"},
    "🩻 MediSync Imaging":      {"color": "#f57c5c", "glyph": "◐", "label": "Imaging"},
    "📰 Health News":           {"color": "#f5a642", "glyph": "◉", "label": "News"},
    "🛡️ Compliance":            {"color": "#7c6fff", "glyph": "◉", "label": "Compliance"},
}

def render_nav():
    """Renders the navigation menu. Call inside `with st.sidebar:` from any page."""
    current_page = st.session_state.get("page_selection", PAGES[0])  # local read for nav highlight

    # Re-inject hide CSS on every rerun (zero-height div so no layout gap)
    st.markdown(
        "<style>"
        "[data-testid='stSidebarNav'],[data-testid='stSidebarNavItems'],"
        "[data-testid='stSidebarNavLink'],section[data-testid='stSidebar'] nav,"
        "section[data-testid='stSidebar']>div>div>div>ul,"
        ".st-emotion-cache-1rtdyuf,.st-emotion-cache-eczf2c,.st-emotion-cache-6tkfeg"
        "{display:none!important;}"
        "section[data-testid='stSidebar']>div:first-child{padding-top:0!important;}"
        "div[data-testid='stSidebarContent']{padding-top:0.5rem!important;}"
        "</style>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "<p style='font-family:Space Mono,monospace;font-size:10px;"
        "letter-spacing:0.12em;color:#3a3a5c;text-transform:uppercase;"
        "margin-bottom:6px;'>▼ Navigation</p>",
        unsafe_allow_html=True,
    )

    for page_name in PAGES:
        meta = PAGE_META.get(page_name, {"color": "#888899", "glyph": "·", "label": page_name})
        is_active = (page_name == current_page)
        color = meta["color"]
        glyph = meta["glyph"]
        label = meta["label"]

        if is_active:
            # Active page: colored filled block, no button (not clickable)
            st.markdown(
                f"""<div style="
                    font-family:'Space Mono',monospace;
                    font-size:13px;
                    font-weight:700;
                    letter-spacing:0.05em;
                    color:{color};
                    background:{color}22;
                    border:1px solid {color}66;
                    border-left:4px solid {color};
                    border-radius:6px;
                    padding:8px 12px;
                    margin-bottom:4px;
                    cursor:default;
                ">{glyph} {label}</div>""",
                unsafe_allow_html=True,
            )
        else:
            if st.button(
                f"{glyph} {label}",
                key=f"nav_{page_name}",
                use_container_width=True,
            ):
                st.session_state.page_selection = page_name
                st.rerun()

# ---------------------------------------------------------------------------
# RESOLVE CURRENT PAGE (global scope — used by sidebar nav AND page router)
# ---------------------------------------------------------------------------
current_page = st.session_state.get("page_selection", PAGES[0])

# ---------------------------------------------------------------------------
# SIDEBAR UI
# ---------------------------------------------------------------------------
with st.sidebar:
    # Navigation — FIRST so all buttons visible without scrolling
    render_nav()

    # API Connection Controller
    col1, col2 = st.columns([1, 4])
    with col1:
        st.markdown("🟢" if st.session_state.api_active else "🔴")
    with col2:
        mode = st.session_state.get("api_mode", "simulation")
        label = {
            "live": "**API – Online (Live)**",
            "simulation": "**API – Online (Sim)**",
        }.get(mode, "**API – Offline**")
        st.markdown(label)

    if not st.session_state.api_active:
        if st.button("🚀 ACTIVATE API", use_container_width=True):
            st.session_state.api_active = True
            st.session_state.api_mode = "simulation"
            add_log("SIMULATION_MODE_ACTIVE")
            st.rerun()
    else:
        if mode == "simulation":
            st.warning("⚡ API Active — Simulation mode")
        else:
            st.success("✅ API Online — Live mode")

        if st.button("🔴 DEACTIVATE", use_container_width=True):
            st.session_state.api_active = False
            st.session_state.api_mode = None
            add_log("API_DEACTIVATED")
            st.rerun()

    # Agent Quick-Launch Panel
    with st.expander("🤖 AGENTS", expanded=True):
        for name, entry in AGENT_REGISTRY.items():
            agent = _get_agent_instance(entry)
            if getattr(agent, "TRIGGER_COMMANDS", []):
                if st.button(
                    f"{agent.icon} {name}",
                    use_container_width=True,
                    key=f"agent_{name}",
                ):
                    cmd = agent.TRIGGER_COMMANDS[0]
                    append_message("user", cmd)

                    with st.status("🤖 Thinking...", expanded=False) as status:
                        reply = agent.run(cmd)
                        status.update(label="🤖 Complete", state="complete")

                    append_message("assistant", reply)
                    st.session_state.page_selection = "💬 Agent Chat"
                    st.rerun()

    # Database and Synchronization Operations
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📥 SYNC", use_container_width=True):
            with st.spinner("Syncing..."):
                sync_from_hf()
                st.rerun()
    with c2:
        if st.button("📤 BACKUP", use_container_width=True):
            with st.spinner("Backing up..."):
                backup_to_hf()
                st.rerun()

    # Header info — moved to bottom so nav has full room at top
    st.markdown("### 🏥 HEALTH_OS_V2")
    st.caption("Health Digital Workforce · AI Agents")

    # AI Model Status
    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        active = get_active_model_label()
        st.caption(f"🤖 AI: {active} (Live)")
    else:
        st.caption("🤖 AI: Offline simulation mode")
        st.error("⚠️ Add GEMINI_API_KEY to .env")

    display_system_logs()

# ---------------------------------------------------------------------------
# PAGE ROUTING LOGIC
# ---------------------------------------------------------------------------
try:
    if current_page == "💬 Agent Chat":
        from pages.chat import render
        render()

    elif current_page == "📊 Health Risk Dashboard":
        from pages.dashboard import render
        render()

    elif current_page == "📄 EHR Summarizer":
        from pages.ehr_summarizer import render
        render()

    elif current_page == "🩻 MediSync Imaging":
        from pages.imaging import render
        render()

    elif current_page == "📰 Health News":
        from pages.news import render
        render()

    elif current_page == "🛡️ Compliance":
        from pages.compliance import render
        render()

    else:
        st.warning("Selected page not found in navigation registry.")

except ImportError as e:
    st.error(f"Module Routing Error: {e}")
    st.info("Please verify the file exists in the /pages directory.")
except Exception as e:
    st.error(f"An unexpected error occurred: {e}")

# --- End of app.py ---
