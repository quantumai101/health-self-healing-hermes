"""
auth/session.py — Session helpers for Hermes Streamlit pages

Token persistence strategy:
- On login: token is stored in st.session_state AND st.query_params
- On refresh: session_state is wiped but query_params survive → token is
  restored from query_params back into session_state automatically.
- On logout: query_params is cleared along with session_state.
- No third-party cookie library needed — st.query_params is built into Streamlit.
"""

import streamlit as st
from auth.auth import validate_session, revoke_session, user_data_path
from pathlib import Path

_TOKEN_PARAM = "t"   # short key keeps the URL tidy


# ---------------------------------------------------------------------------
# Core persistence — called once at top of app.py every page load
# ---------------------------------------------------------------------------

def restore_session_from_cookie():
    """
    Restore auth_token from query_params into session_state if missing.
    Call this at the very top of app.py before any auth check.
    Name kept identical so app.py needs no changes.
    """
    if st.session_state.get("auth_token"):
        return  # already in memory, nothing to do

    token = st.query_params.get(_TOKEN_PARAM)
    if token:
        st.session_state["auth_token"] = token


def _cookie_manager():
    """
    Stub — kept so app.py import of _cookie_manager() doesn't break.
    No-op: query_params strategy needs no cookie manager instance.
    """
    return None


def persist_login(token: str):
    """
    Call this after a successful login instead of setting auth_token directly.
    Writes token to both session_state and query_params so it survives refresh.
    """
    st.session_state["auth_token"] = token
    st.query_params[_TOKEN_PARAM] = token


def _clear_token():
    """Remove token from query_params on logout or expiry."""
    try:
        del st.query_params[_TOKEN_PARAM]
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core auth functions
# ---------------------------------------------------------------------------

def require_auth():
    """
    Gate every page behind authentication.
    Returns the current user dict if authenticated, otherwise stops.
    """
    restore_session_from_cookie()

    token = st.session_state.get("auth_token")
    if not token:
        _redirect_to_login()
        st.stop()

    user = validate_session(token)
    if not user:
        st.session_state.clear()
        _clear_token()
        st.warning("Your session has expired. Please sign in again.")
        _redirect_to_login()
        st.stop()

    st.session_state["auth_user"] = user
    return user


def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def current_user_data_path(subdir: str = "") -> Path:
    user = current_user()
    if not user:
        raise RuntimeError("No authenticated user in session.")
    return user_data_path(user["id"], subdir)


def logout():
    """Revoke server-side session, clear query param, and wipe all state."""
    token = st.session_state.get("auth_token")
    if token:
        revoke_session(token)
    _clear_token()
    st.session_state.clear()
    st.rerun()


def render_user_sidebar():
    user = current_user()
    if not user:
        return

    with st.sidebar:
        st.divider()
        st.markdown(f"**{user['name']}**")
        st.caption(user["email"])
        mfa_status = "🔐 MFA on" if user["mfa_enabled"] else "⚠️ MFA off"
        st.caption(mfa_status)
        if st.button("Sign out", use_container_width=True):
            logout()


def _redirect_to_login():
    st.session_state["show_login"] = True
