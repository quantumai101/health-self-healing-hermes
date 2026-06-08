"""
pages/login.py — Hermes Login & MFA Setup Page
MFA is mandatory for all users on every login.
"""

import streamlit as st
from auth.auth import (
    init_db, create_user, verify_password,
    setup_totp, verify_totp_and_enable, verify_totp_code,
    create_session, get_user_by_id
)


def render():
    init_db()

    st.markdown("""
        <div style="text-align:center; padding: 2rem 0 1rem;">
            <div style="font-size:2.5rem;">🛡️</div>
            <h1 style="font-size:2rem; font-weight:700; letter-spacing:0.08em;">HEALTH HERMES</h1>
            <p style="color:#888; font-size:1rem;">Your private medical AI assistant</p>
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
    elif step == "force_mfa_setup":
        _step_force_mfa_setup()
    elif step == "force_mfa_verify":
        _step_force_mfa_verify()


def _step_credentials():
    with st.form("login_form"):
        email = st.text_input(
            "Email address",
            placeholder="you@example.com",
            autocomplete="off"
        ,
    key="login_email_address_k"
)
        password = st.text_input(
            "Password",
            type="password",
            autocomplete="new-password"
        ,
    key="login_password_k"
)
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
            st.session_state["login_step"] = "force_mfa_setup"
            st.rerun()


def _step_mfa():
    """Standard MFA verification step on every login."""
    user_id = st.session_state.get("pending_user_id")

    st.markdown("""
        <div style="background:#1a1a2e;border:1px solid #f5c842;border-radius:10px;
        padding:1rem 1.2rem;margin-bottom:1rem;">
            <p style="color:#f5c842;font-weight:700;margin:0;">🔐 Two-Factor Authentication Required</p>
            <p style="color:#aaa;font-size:0.9rem;margin:0.3rem 0 0;">
                Open your authenticator app (Microsoft Authenticator, Google Authenticator, or Authy)
                and enter the 6-digit code shown for <b>Health Hermes</b>.
            </p>
        </div>
    """, unsafe_allow_html=True)

    with st.form("mfa_form"):
        code = st.text_input(
            "6-digit authentication code",
            max_chars=10,
            placeholder="123456",
            help="Enter the code from your authenticator app, or a backup code.",
            autocomplete="off"
        ,
    key="login_6_digit_authentication_k"
)
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
            st.error("❌ Invalid or expired code. Please try again.")
            st.caption("Make sure your device clock is synced. Codes refresh every 30 seconds.")


def _step_force_mfa_setup():
    """
    Shown when an existing user has no MFA set up.
    Reuses the existing DB secret on refresh to avoid QR mismatch.
    """
    import pyotp, qrcode
    from io import BytesIO

    user_id = st.session_state["pending_user_id"]

    st.warning("🔐 **MFA setup is required** to access Health Hermes.")
    st.markdown("""
        For your security, two-factor authentication is **mandatory**.
        Please scan the QR code below with your authenticator app:
        - **Microsoft Authenticator** (recommended)
        - Google Authenticator
        - Authy
    """)

    if "totp_setup_data" not in st.session_state:
        user = get_user_by_id(user_id)
        if user.get("totp_secret"):
            # Reuse existing secret — prevents new QR being generated on every refresh
            totp = pyotp.TOTP(user["totp_secret"])
            uri = totp.provisioning_uri(name=user["email"], issuer_name="Health Hermes")
            qr = qrcode.QRCode(box_size=6, border=2)
            qr.add_data(uri)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            st.session_state["totp_setup_data"] = {
                "secret": user["totp_secret"],
                "qr_png": buf.getvalue(),
                "backup_codes": [],
            }
        else:
            # First time — generate a fresh secret and save to DB
            st.session_state["totp_setup_data"] = setup_totp(user_id)

    data = st.session_state["totp_setup_data"]
    st.image(data["qr_png"], width=200)

    if st.button("I've scanned it — Continue →", use_container_width=True, key="login_i_btn"):
        st.session_state["login_step"] = "force_mfa_verify"
        st.rerun()


def _step_force_mfa_verify():
    """Verify the TOTP code after forced MFA setup."""
    user_id = st.session_state["pending_user_id"]

    st.info("Enter the 6-digit code from your authenticator app to confirm setup.")

    with st.form("force_verify_form"):
        code = st.text_input(
            "Code from app",
            max_chars=6,
            placeholder="123456",
            autocomplete="off"
        ,
    key="login_code_from_app_k"
)
        submitted = st.form_submit_button("Enable MFA & Sign In →", use_container_width=True)

    if submitted:
        if verify_totp_and_enable(user_id, code):
            st.success("✅ MFA enabled! Signing you in...")
            _finalize_login(user_id)
        else:
            st.error("Code didn't match. Make sure your device clock is synced and try again.")


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
        name = st.text_input("Full name",
    key="login_full_name_k"
)
        email = st.text_input("Email address", placeholder="you@example.com",
    key="login_email_address_k1"
)
        pw1 = st.text_input("Password", type="password",
    key="login_password_k1"
)
        pw2 = st.text_input("Confirm password", type="password",
    key="login_confirm_password_k"
)
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
    """MFA setup during registration — mandatory, no skip option."""
    user_id = st.session_state["pending_user_id"]

    st.success("✅ Account created!")
    st.markdown("""
        **Set up two-factor authentication** to secure your account.
        Scan the QR code below with your authenticator app:
        - **Microsoft Authenticator** (recommended)
        - Google Authenticator
        - Authy
    """)

    if "totp_setup_data" not in st.session_state:
        st.session_state["totp_setup_data"] = setup_totp(user_id)

    data = st.session_state["totp_setup_data"]
    st.image(data["qr_png"], width=200)

    st.info("Once scanned, click Continue to verify your setup.")

    if st.button("I've scanned it — Continue →", use_container_width=True, key="login_i_btn_2"):
        st.session_state["register_step"] = "mfa_verify"
        st.rerun()


def _step_mfa_verify():
    """Verify TOTP code after registration MFA setup."""
    user_id = st.session_state["pending_user_id"]
    st.info("Enter the 6-digit code from your authenticator app to confirm setup.")

    with st.form("verify_form"):
        code = st.text_input(
            "Code from app",
            max_chars=6,
            placeholder="123456",
            autocomplete="off"
        ,
    key="login_code_from_app_k1"
)
        submitted = st.form_submit_button("Enable MFA & Sign In →", use_container_width=True)

    if submitted:
        if verify_totp_and_enable(user_id, code):
            st.success("🎉 MFA enabled! Signing you in...")
            _finalize_login(user_id)
        else:
            st.error("Code didn't match. Make sure your device clock is synced and try again.")


# ── Finalize login ────────────────────────────────────────────────────────────

def _finalize_login(user_id: str):
    user = get_user_by_id(user_id)
    token = create_session(user_id)

    # Clear stale imaging cache
    keys_to_clear = [k for k in st.session_state.keys() if k.startswith("img_")]
    for k in keys_to_clear:
        del st.session_state[k]

    # Persist token to cookie + session_state
    from auth.session import persist_login
    persist_login(token)
    st.session_state["auth_user"] = user

    # Clean up login/register flow keys
    for k in ["register_step", "login_step", "pending_user_id", "totp_setup_data", "show_login"]:
        st.session_state.pop(k, None)

    st.rerun()
