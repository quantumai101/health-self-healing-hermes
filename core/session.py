"""
core/session.py
Streamlit session state helpers shared across all pages and agents.
Uses dict-style access throughout for compatibility with test mocks.
"""

from datetime import datetime
import streamlit as st


def init_session() -> None:
    """Initialise all session state keys. Call once at app.py startup."""
    defaults = {
        "messages":            [],
        "api_active":          True,
        "api_mode":            "simulation",
        "logs":                [],
        "page_selection":      "💬 Agent Chat",
        "active_gemini_model": "Gemini 3 Flash",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_log(msg: str) -> None:
    """Prepend a timestamped log entry. Keeps last 10 entries. Never crashes."""
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []
        ts = datetime.now().strftime("%H:%M:%S")
        logs = list(st.session_state["logs"])
        logs.insert(0, f"[{ts}] {msg}")
        st.session_state["logs"] = logs[:10]
    except Exception:
        pass  # Logging must never crash the app or tests


def get_logs() -> list:
    try:
        return st.session_state.get("logs", [])
    except Exception:
        return []


def append_message(role: str, content: str) -> None:
    try:
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
        st.session_state["messages"].append({"role": role, "content": content})
    except Exception:
        pass


def get_messages() -> list:
    try:
        return st.session_state.get("messages", [])
    except Exception:
        return []


def clear_messages() -> None:
    try:
        st.session_state["messages"] = []
    except Exception:
        pass
