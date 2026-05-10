"""
pages/login.py — Hermes Login & MFA Setup Page
"""

import token

import streamlit as st
from auth.auth import (
    init_db, create_user, verify_password,
    setup_totp, verify_totp_and_enable, verify_totp_code,
    create_session
)


def render():
    init_db()

    st.markdown("""
        <div style="text-align:center; padding: 2rem 0 1rem;">
            <h1 style="font-size:2rem; font-weight:600;">🛡️ HEALTH HERMES</h1>
            <p style="color: #888; font-size:1rem;">Your private medical AI assistant</p>
        </div>
    """, unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Sign in", "Create account"])

    with tab_login:
        _login_flow()

    with tab_register:
        _register_flow()


# ── Login flow ────────────────────────────────────────────────────────────────

def _login_flow():
    step = st.session_state.get("login_step", "credentials")
    if step == "credentials":
        _step_credentials()
    elif step == "mfa":
        _step_mfa()


def _step_credentials():
    with st.form("login_form"):
        email = st.text_input("Email address", placeholder="you@example.com")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Continue →", use_container_width=True)

    if submitted:
        if not email or not password:
            st.error("Please enter your email and password.")
            return
        user = verify_password(email, password)
        if not user:
            st.error("Invalid email or password.")
            return
        st.session_state["pending_user_id"] = user["id"]
        if user["mfa_enabled"]:
            st.session_state["login_step"] = "mfa"
            st.rerun()
        else:
            _finalize_login(user["id"])


def _step_mfa():
    user_id = st.session_state.get("pending_user_id")
    st.info("🔐 Enter the 6-digit code from your authenticator app (or a backup code).")

    with st.form("mfa_form"):
        code = st.text_input("Authentication code", max_chars=10, placeholder="123456")
        col1, col2 = st.columns(2)
        submitted = col1.form_submit_button("Verify →", use_container_width=True)
        back = col2.form_submit_button("← Back", use_container_width=True)

    if back:
        st.session_state["login_step"] = "credentials"
        st.session_state.pop("pending_user_id", None)
        st.rerun()

    if submitted:
        if not code:
            st.error("Please enter your authentication code.")
            return
        if verify_totp_code(user_id, code):
            _finalize_login(user_id)
        else:
            st.error("Invalid or expired code. Please try again.")


# ── Register flow ─────────────────────────────────────────────────────────────

def _register_flow():
    step = st.session_state.get("register_step", "details")
    if step == "details":
        _step_register_details()
    elif step == "mfa_setup":
        _step_mfa_setup()
    elif step == "mfa_verify":
        _step_mfa_verify()


def _step_register_details():
    with st.form("register_form"):
        name = st.text_input("Full name")
        email = st.text_input("Email address", placeholder="you@example.com")
        pw1 = st.text_input("Password", type="password")
        pw2 = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Create account →", use_container_width=True)

    if submitted:
        if not name or not email or not pw1:
            st.error("All fields are required.")
            return
        if pw1 != pw2:
            st.error("Passwords don't match.")
            return
        try:
            user = create_user(email, name, pw1)
            st.session_state["pending_user_id"] = user["id"]
            st.session_state["register_step"] = "mfa_setup"
            st.rerun()
        except ValueError as e:
            st.error(str(e))


def _step_mfa_setup():
    user_id = st.session_state["pending_user_id"]
    st.success("✅ Account created! Set up two-factor authentication.")
    st.markdown("Scan this QR code with **Google Authenticator**, **Authy**, or any TOTP app.")

    if "totp_setup_data" not in st.session_state:
        st.session_state["totp_setup_data"] = setup_totp(user_id)

    data = st.session_state["totp_setup_data"]
    st.image(data["qr_png"], width=220)

    with st.expander("Can't scan? Enter code manually"):
        st.code(data["secret"], language=None)

    with st.expander("🔑 Save your backup codes (one-time use)"):
        st.warning("Store these somewhere safe. Each can be used once if you lose your phone.")
        st.code("\n".join(data["backup_codes"]), language=None)

    col1, col2 = st.columns(2)
    if col1.button("Continue →", use_container_width=True):
        st.session_state["register_step"] = "mfa_verify"
        st.rerun()
    if col2.button("Skip for now", use_container_width=True):
        _finalize_login(user_id)


def _step_mfa_verify():
    user_id = st.session_state["pending_user_id"]
    st.info("Enter the 6-digit code from your authenticator to confirm setup.")

    with st.form("verify_form"):
        code = st.text_input("Code from app", max_chars=6, placeholder="123456")
        submitted = st.form_submit_button("Enable MFA →", use_container_width=True)

    if submitted:
        if verify_totp_and_enable(user_id, code):
            st.success("🎉 MFA enabled!")
            _finalize_login(user_id)
        else:
            st.error("Code didn't match. Make sure your device clock is synced and try again.")


# ── Finalize login ────────────────────────────────────────────────────────────

def _finalize_login(user_id: str):
    from auth.auth import get_user_by_id
    user = get_user_by_id(user_id)
    token = create_session(user_id)

    # ✅ Clear ALL stale imaging/session cache so scans reload fresh from disk
    keys_to_clear = [k for k in st.session_state.keys() if k.startswith("img_")]
    for k in keys_to_clear:
        del st.session_state[k]

    # Set auth state
    # st.session_state["auth_token"] = token
    from auth.session import persist_login
    persist_login(token)
    st.session_state["auth_user"] = user

    # Clean up login flow keys
    for k in ["register_step", "login_step", "pending_user_id", "totp_setup_data", "show_login"]:
        st.session_state.pop(k, None)

    st.rerun()
