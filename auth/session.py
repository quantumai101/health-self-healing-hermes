"""
auth/session.py — Session helpers for Hermes Streamlit pages

Token persistence strategy:
- On login: token stored in st.session_state AND st.query_params
- On refresh: session_state wiped but query_params survive → token restored
- On logout/expiry: query_params cleared along with session_state
- Idle timeout: 60 minutes (1 hour) — increased from 10 min for usability
- No third-party cookie library needed — st.query_params is built into Streamlit

FIX (2026-06-03):
- Idle timeout extended from 10 → 60 minutes so normal page refreshes
  and tab switching never force a logout mid-session.
- restore_session_from_cookie() now always runs BEFORE any timeout check,
  so last_active is recovered from query_params before (now - last_active)
  is evaluated. This eliminates the false-logout-on-refresh bug entirely.
- DEV_MODE env var still disables idle timeout entirely during development.

FIX (2026-05-14):
- Streamlit hot-reload during development wipes session_state["last_active"].
  Previously this caused an immediate forced logout on every file-save.
  Solution: last_active is now persisted in st.query_params alongside the
  auth token, so it survives hot-reloads exactly like the token does.
"""

import os
import time
import streamlit as st
from auth.auth import validate_session, revoke_session, user_data_path
from pathlib import Path

_TOKEN_PARAM  = "t"         # short key keeps the URL tidy
_ACTIVE_PARAM = "la"        # last_active timestamp persisted in query_params

# ── CHANGED: 10 min → 60 min ─────────────────────────────────────────────────
IDLE_SECONDS  = 60 * 60     # 1 hour — comfortable for medical record review

# ── Set DEV_MODE=true in your .env to disable idle timeout while developing ──
DEV_MODE = os.getenv("DEV_MODE", "false").lower() in ("true", "1", "yes")


# ─────────────────────────────────────────────────────────────────────────────
# Core persistence
# ─────────────────────────────────────────────────────────────────────────────

def restore_session_from_cookie():
    """
    Restore auth_token AND last_active from query_params into session_state
    if missing (i.e. after a Streamlit page refresh or hot-reload).

    CRITICAL: this must be called at the very top of require_auth() —
    BEFORE any idle-timeout arithmetic — so that last_active is always
    populated from query_params before (now - last_active) is evaluated.
    A missing last_active was the root cause of false logouts on refresh.
    """
    # Restore auth token
    if not st.session_state.get("auth_token"):
        token = st.query_params.get(_TOKEN_PARAM)
        if token:
            st.session_state["auth_token"] = token

    # Restore last_active — prevents (now - None) crash and false timeout
    if not st.session_state.get("last_active"):
        la_str = st.query_params.get(_ACTIVE_PARAM)
        if la_str:
            try:
                st.session_state["last_active"] = float(la_str)
            except ValueError:
                pass
        else:
            # No stored timestamp at all → treat as fresh login, grant window
            # This handles the case where a user bookmarked the app without
            # a ?la= param in the URL.
            st.session_state["last_active"] = time.time()


def _cookie_manager():
    """Stub — kept so any legacy import in app.py doesn't break."""
    return None


def persist_login(token: str):
    """
    Call after successful login. Writes token to session_state AND
    query_params so it survives page refresh and hot-reload.
    Also initialises the idle-timeout clock in both places.
    """
    now = time.time()
    st.session_state["auth_token"]  = token
    st.session_state["last_active"] = now
    st.query_params[_TOKEN_PARAM]   = token
    st.query_params[_ACTIVE_PARAM]  = str(now)


def _clear_token():
    """Remove token and last_active from query_params on logout or expiry."""
    for param in (_TOKEN_PARAM, _ACTIVE_PARAM):
        try:
            del st.query_params[param]
        except Exception:
            pass


def _update_active_timestamp():
    """Refresh last_active in both session_state and query_params."""
    now = time.time()
    st.session_state["last_active"] = now
    st.query_params[_ACTIVE_PARAM]  = str(now)


# ─────────────────────────────────────────────────────────────────────────────
# Core auth functions
# ─────────────────────────────────────────────────────────────────────────────

def require_auth():
    """
    Gate every page behind authentication.
    Enforces:
      1. Token presence
      2. 60-minute idle timeout — SKIPPED when DEV_MODE=true in .env
      3. JWT validity via DB session check

    Page refresh NEVER triggers logout because:
      - restore_session_from_cookie() runs first, recovering last_active
        from query_params before any timeout check occurs.
      - IDLE_SECONDS is now 3600 (1 hour) so normal tab switching,
        reading, and form filling don't expire the session.

    Returns the current user dict if all checks pass, otherwise stops.
    """
    # ── MUST be first — recovers last_active before timeout check ────────────
    restore_session_from_cookie()

    token = st.session_state.get("auth_token")
    if not token:
        _redirect_to_login()
        st.stop()

    # ── Idle timeout ──────────────────────────────────────────────────────────
    if DEV_MODE:
        _update_active_timestamp()
        _show_dev_mode_badge()
    else:
        _check_idle_timeout()

    # ── JWT + DB session validity ─────────────────────────────────────────────
    user = validate_session(token)
    if not user:
        st.session_state.clear()
        _clear_token()
        st.warning("⏱️ Your session has expired. Please sign in again.")
        _redirect_to_login()
        st.stop()

    st.session_state["auth_user"] = user
    return user


def _check_idle_timeout():
    """
    Enforce the 60-minute idle timeout.

    last_active is always populated before this runs (via
    restore_session_from_cookie), so the (now - None) false-logout
    on page refresh cannot occur.
    """
    now         = time.time()
    last_active = st.session_state.get("last_active")

    if last_active is None:
        # Fallback safety — should never reach here after restore above
        _update_active_timestamp()
    elif (now - last_active) > IDLE_SECONDS:
        _force_logout_idle()
    else:
        _update_active_timestamp()


def _show_dev_mode_badge():
    """Subtle sidebar reminder that idle timeout is disabled."""
    st.sidebar.caption("🛠️ DEV MODE — idle timeout disabled")


def _force_logout_idle():
    """Log out a user who exceeded the 60-minute idle timeout."""
    token = st.session_state.get("auth_token")
    if token:
        revoke_session(token)
    _clear_token()
    st.session_state.clear()
    st.warning("⏱️ You were automatically logged out after 60 minutes of inactivity.")
    _redirect_to_login()
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def current_user() -> dict | None:
    return st.session_state.get("auth_user")


def current_user_data_path(subdir: str = "") -> Path:
    user = current_user()
    if not user:
        raise RuntimeError("No authenticated user in session.")
    return user_data_path(user["id"], subdir)


def logout():
    """Revoke server-side session, clear query params, and wipe all state."""
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

        if DEV_MODE:
            st.caption("🛠️ DEV MODE active")

        if st.button("Sign out", use_container_width=True):
            logout()


def _redirect_to_login():
    st.session_state["show_login"] = True
