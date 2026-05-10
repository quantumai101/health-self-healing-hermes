"""
auth/session.py — Session helpers for Hermes Streamlit pages

Fix: auth_token is now persisted in a browser cookie so page refreshes
don't log the user out. On every load we attempt to restore the token
from the cookie before require_auth() checks session_state.
"""

import streamlit as st
from auth.auth import validate_session, revoke_session, user_data_path
from pathlib import Path

# ---------------------------------------------------------------------------
# Cookie manager — pip install extra-streamlit-components
# ---------------------------------------------------------------------------
try:
    import extra_streamlit_components as stx
    _COOKIES_AVAILABLE = True
except ImportError:
    _COOKIES_AVAILABLE = False

_COOKIE_NAME = "hermes_auth_token"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days in seconds


@st.cache_resource
def _get_cookie_manager():
    """
    Cache the CookieManager so only ONE instance is created per app run.
    Multiple instances cause Streamlit component conflicts.
    """
    return stx.CookieManager(key="hermes_cookie_manager")


def _cookie_manager():
    """Return the cached CookieManager, or None if unavailable."""
    if not _COOKIES_AVAILABLE:
        return None
    return _get_cookie_manager()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def restore_session_from_cookie():
    """
    Call this ONCE at the very top of app.py, before require_auth().

    If session_state has no auth_token but a valid cookie exists,
    the token is restored into session_state so the rest of the app
    behaves as if the user never left.
    """
    if st.session_state.get("auth_token"):
        return  # already set, nothing to do

    cm = _cookie_manager()
    if cm is None:
        return  # cookie support not installed

    token = cm.get(_COOKIE_NAME)
    if token:
        st.session_state["auth_token"] = token


def _save_token_to_cookie(token: str):
    """Persist token in browser cookie after a successful login."""
    cm = _cookie_manager()
    if cm is None:
        return
    cm.set(_COOKIE_NAME, token, max_age=_COOKIE_MAX_AGE)


def _clear_cookie():
    """Delete the auth cookie on logout."""
    cm = _cookie_manager()
    if cm is None:
        return
    cm.delete(_COOKIE_NAME)


def persist_login(token: str):
    """
    Call this from your login page right after a successful authentication
    instead of setting auth_token directly, so the cookie is also written.

    Example (pages/login.py):
        from auth.session import persist_login
        persist_login(token)
        st.rerun()
    """
    st.session_state["auth_token"] = token
    _save_token_to_cookie(token)


# ---------------------------------------------------------------------------
# Core auth functions (unchanged API, extended implementation)
# ---------------------------------------------------------------------------

def require_auth():
    """
    Gate every page behind authentication.
    Returns the current user dict if authenticated, otherwise stops.
    """
    # Attempt cookie restore first (covers refresh scenario)
    restore_session_from_cookie()

    token = st.session_state.get("auth_token")
    if not token:
        _redirect_to_login()
        st.stop()

    user = validate_session(token)
    if not user:
        # Token invalid/expired — clean up everything
        st.session_state.clear()
        _clear_cookie()
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
    """Revoke server-side session, clear cookie, and wipe all state."""
    token = st.session_state.get("auth_token")
    if token:
        revoke_session(token)
    _clear_cookie()
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
