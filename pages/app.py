"""
app.py — Entry Point Only
health-self-healing-hermes
AGENTS.md Phase 2 scaffold.

This file only: sets page config, loads CSS, initialises session,
renders sidebar, and routes to the correct page module.
No business logic lives here.
"""

# --- SQLITE HACK (required for cloud DuckDB) ---
try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass

import os
from dotenv import load_dotenv
load_dotenv()

import streamlit as st
from core.config import APP_TITLE, APP_ICON, UI_CSS, PAGES
from core.session import init_session, add_log, get_logs
from core.db import load_synthetic_data, sync_from_hf, backup_to_hf
from core.gemini import get_active_model_label
from agents import AGENT_REGISTRY

# ---------------------------------------------------------------------------
# PAGE CONFIG (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(page_title=APP_TITLE, page_icon=APP_ICON, layout="wide")
st.markdown(UI_CSS, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SESSION & DB INIT
# ---------------------------------------------------------------------------
init_session()
load_synthetic_data()

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🏥 HEALTH_OS_V2")
    st.caption("Health Digital Workforce · AI Agents")

    gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if gemini_key:
        active = get_active_model_label()
        st.caption(f"🤖 AI: {active} (Live)")
    else:
        st.caption("🤖 AI: Offline simulation mode")
        st.error("⚠️ Add GEMINI_API_KEY to .env or HF Secrets")

    st.divider()

    # API status indicator
    col1, col2 = st.columns([1, 4])
    with col1:
        st.markdown("🟢" if st.session_state.api_active else "🔴")
    with col2:
        mode = st.session_state.get("api_mode", "simulation")
        label = {
            "live":       "**API – Online (Live)**",
            "simulation": "**API – Online (Sim)**",
        }.get(mode, "**API – Offline**")
        st.markdown(label)

    if not st.session_state.api_active:
        if st.button("🚀 ACTIVATE API", use_container_width=True):
            st.session_state.api_active = True
            st.session_state.api_mode   = "simulation"
            add_log("SIMULATION_MODE_ACTIVE")
            st.rerun()
    else:
        if mode == "simulation":
            st.warning("⚡ API Active — Simulation mode")
        else:
            st.success("✅ API Online — Live mode")
        if st.button("🔴 DEACTIVATE", use_container_width=True):
            st.session_state.api_active = False
            st.session_state.api_mode   = None
            add_log("API_DEACTIVATED")
            st.rerun()

    st.divider()

    # Navigation
    st.markdown("### ▼ NAVIGATION")
    page = st.selectbox(
        "WORKSPACE", PAGES,
        index=PAGES.index(st.session_state.page_selection),
        label_visibility="collapsed",
        key="page_select",
    )
    st.session_state.page_selection = page

    st.divider()

    # Agent quick-launch buttons
    with st.expander("🤖 AGENTS", expanded=True):
        for name, agent in AGENT_REGISTRY.items():
            if agent.TRIGGER_COMMANDS:
                if st.button(
                    f"{agent.icon} {name}",
                    use_container_width=True,
                    key=f"agent_{name}",
                ):
                    cmd = agent.TRIGGER_COMMANDS[0]
                    from core.session import append_message
                    append_message("user", cmd)
                    reply = agent.run(cmd)
                    append_message("assistant", reply)
                    st.session_state.page_selection = "💬 Agent Chat"
                    st.rerun()

    st.divider()

    # DB sync / backup
    c1, c2 = st.columns(2)
    with c1:
        if st.button("📥 SYNC", use_container_width=True):
            sync_from_hf(); st.rerun()
    with c2:
        if st.button("📤 BACKUP", use_container_width=True):
            backup_to_hf(); st.rerun()

    logs = get_logs()
    if logs:
        st.code("\n".join(logs), language="bash")
    else:
        st.caption("Ready")

# ---------------------------------------------------------------------------
# PAGE ROUTING
# ---------------------------------------------------------------------------
if page == "💬 Agent Chat":
    from pages.chat import render
    render()

elif page == "📊 Health Risk Dashboard":
    from pages.dashboard import render
    render()

elif page == "📄 EHR Summarizer":
    from pages.ehr_summarizer import render
    render()

elif page == "🩻 MediSync Imaging":
    from pages.imaging import render
    render()

elif page == "📰 Health News":
    from pages.news import render
    render()

elif page == "🛡️ Compliance":
    from pages.compliance import render
    render()
