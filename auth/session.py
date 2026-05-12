"""
auth/session.py — Session helpers for Hermes Streamlit pages

Token persistence strategy:
- On login: token stored in st.session_state AND st.query_params
- On refresh: session_state wiped but query_params survive → token restored
- On logout/expiry: query_params cleared along with session_state
- Idle timeout: 10 minutes (matches My Health Record / APRA standard)
- No third-party cookie library needed — st.query_params is built into Streamlit
"""

import time
import streamlit as st
from auth.auth import validate_session, revoke_session, user_data_path
from pathlib import Path

_TOKEN_PARAM  = "t"    # short key keeps the URL tidy
IDLE_SECONDS  = 10 * 60  # 10 minutes — Australian health/finance standard


# ---------------------------------------------------------------------------
# Core persistence
# ---------------------------------------------------------------------------

def restore_session_from_cookie():
    """
    Restore auth_token from query_params into session_state if missing.
    Called at the very top of app.py before any auth check.
    """
    if st.session_state.get("auth_token"):
        return
    token = st.query_params.get(_TOKEN_PARAM)
    if token:
        st.session_state["auth_token"] = token


def _cookie_manager():
    """Stub — kept so any legacy import in app.py doesn't break."""
    return None


def persist_login(token: str):
    """
    Call after successful login. Writes token to session_state AND
    query_params so it survives page refresh.
    Also initialises the idle-timeout clock.
    """
    st.session_state["auth_token"] = token
    st.session_state["last_active"] = time.time()
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
    Enforces:
      1. Token presence
      2. 10-minute idle timeout (Australian health/finance standard)
      3. JWT validity via DB session check
    Returns the current user dict if all checks pass, otherwise stops.
    """
    restore_session_from_cookie()

    token = st.session_state.get("auth_token")
    if not token:
        _redirect_to_login()
        st.stop()

    # ── Idle timeout check ───────────────────────────────────────────────────
    now = time.time()
    last_active = st.session_state.get("last_active")

    if last_active is None:
        # First load after refresh — restore the clock so they get a fresh window
        st.session_state["last_active"] = now
    elif (now - last_active) > IDLE_SECONDS:
        # User exceeded idle limit — force logout
        _force_logout_idle()

    # Update activity timestamp on every authenticated page load
    st.session_state["last_active"] = now
    # ────────────────────────────────────────────────────────────────────────

    # ── JWT + DB session validity ────────────────────────────────────────────
    user = validate_session(token)
    if not user:
        st.session_state.clear()
        _clear_token()
        st.warning("⏱️ Your session has expired. Please sign in again.")
        _redirect_to_login()
        st.stop()

    st.session_state["auth_user"] = user
    return user


def _force_logout_idle():
    """Log out a user who exceeded the idle timeout."""
    token = st.session_state.get("auth_token")
    if token:
        revoke_session(token)
    _clear_token()
    st.session_state.clear()
    st.warning("⏱️ You were automatically logged out after 10 minutes of inactivity.")
    _redirect_to_login()
    st.stop()


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
