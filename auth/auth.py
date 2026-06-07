"""
auth/auth.py — Hermes Authentication & MFA Module
Handles: user registration, bcrypt passwords, TOTP MFA, JWT sessions, per-user data paths.

Session policy (Australian health/finance standard):
- JWT absolute expiry: 8 hours
- Idle timeout: 10 minutes (enforced in auth/session.py)
"""

import os
import sqlite3
import hashlib
import secrets
import base64
import time
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

import bcrypt
import pyotp
import qrcode
import jwt
from io import BytesIO

# ── Config ──────────────────────────────────────────────────────────────────

# -- DB path -- HF Persistent Volume routing (patched by agent) --
_DATA_DIR = Path("/data")
DB_PATH   = (_DATA_DIR / "users.db") if _DATA_DIR.exists() else (Path(__file__).parent / "users.db")
DATA_ROOT        = Path(__file__).parent.parent / "data" / "users"
JWT_SECRET       = os.getenv("HERMES_JWT_SECRET", secrets.token_hex(32))
JWT_ALGO         = "HS256"
JWT_EXPIRE_HOURS = 8    # absolute maximum — idle timeout (10 min) kicks in first
APP_NAME         = "Health Hermes"

# ── Database ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Call once at app startup."""
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              TEXT PRIMARY KEY,
            email           TEXT UNIQUE NOT NULL,
            name            TEXT NOT NULL,
            password_hash   TEXT NOT NULL,
            totp_secret     TEXT,
            mfa_enabled     INTEGER DEFAULT 0,
            backup_codes    TEXT,
            created_at      TEXT NOT NULL,
            last_login      TEXT
        );

        CREATE TABLE IF NOT EXISTS sessions (
            token_id    TEXT PRIMARY KEY,
            user_id     TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            expires_at  TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        """)
    DATA_ROOT.mkdir(parents=True, exist_ok=True)

# ── User management ───────────────────────────────────────────────────────────

def create_user(email: str, name: str, password: str) -> dict:
    """Register a new user. Returns user dict or raises ValueError."""
    if get_user_by_email(email):
        raise ValueError("Email already registered.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    user_id  = "usr_" + secrets.token_urlsafe(12)
    pw_hash  = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now      = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?,?,?,?,?)",
            (user_id, email.lower().strip(), name, pw_hash, now)
        )

    user_dir = DATA_ROOT / user_id
    (user_dir / "scans").mkdir(parents=True, exist_ok=True)
    (user_dir / "reports").mkdir(parents=True, exist_ok=True)
    (user_dir / "ehr").mkdir(parents=True, exist_ok=True)

    return get_user_by_id(user_id)


def get_user_by_email(email: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email=?", (email.lower().strip(),)
        ).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(row) if row else None


def verify_password(email: str, password: str) -> dict | None:
    """Returns user dict if credentials valid, else None."""
    user = get_user_by_email(email)
    if not user:
        return None
    if bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return user
    return None

# ── TOTP MFA ─────────────────────────────────────────────────────────────────

def setup_totp(user_id: str) -> dict:
    """Generate a new TOTP secret. Returns secret + QR PNG bytes + backup codes."""
    secret = pyotp.random_base32()
    user   = get_user_by_id(user_id)

    totp              = pyotp.TOTP(secret)
    provisioning_uri  = totp.provisioning_uri(name=user["email"], issuer_name=APP_NAME)

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(provisioning_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    qr_bytes = buf.getvalue()

    raw_codes    = [secrets.token_hex(4).upper() for _ in range(8)]
    hashed_codes = [hashlib.sha256(c.encode()).hexdigest() for c in raw_codes]

    with get_db() as conn:
        conn.execute(
            "UPDATE users SET totp_secret=?, backup_codes=? WHERE id=?",
            (secret, json.dumps(hashed_codes), user_id)
        )

    return {
        "secret":           secret,
        "qr_png":           qr_bytes,
        "backup_codes":     raw_codes,
        "provisioning_uri": provisioning_uri,
    }


def verify_totp_and_enable(user_id: str, code: str) -> bool:
    """Verify a TOTP code and enable MFA on success."""
    user = get_user_by_id(user_id)
    if not user or not user["totp_secret"]:
        return False
    totp = pyotp.TOTP(user["totp_secret"])
    if totp.verify(code.strip(), valid_window=2):
        with get_db() as conn:
            conn.execute("UPDATE users SET mfa_enabled=1 WHERE id=?", (user_id,))
        return True
    return False


def verify_totp_code(user_id: str, code: str) -> bool:
    """Verify TOTP code during login (supports backup codes)."""
    user = get_user_by_id(user_id)
    if not user or not user["totp_secret"]:
        return False

    totp = pyotp.TOTP(user["totp_secret"])
    if totp.verify(code.strip(), valid_window=2):
        return True

    # Check backup codes
    code_hash = hashlib.sha256(code.strip().upper().encode()).hexdigest()
    codes = json.loads(user["backup_codes"] or "[]")
    if code_hash in codes:
        codes.remove(code_hash)
        with get_db() as conn:
            conn.execute(
                "UPDATE users SET backup_codes=? WHERE id=?",
                (json.dumps(codes), user_id)
            )
        return True

    return False

# ── JWT Sessions ─────────────────────────────────────────────────────────────

def create_session(user_id: str) -> str:
    """Issue a signed JWT for this user. Absolute expiry = 8 hours."""
    token_id = secrets.token_urlsafe(16)
    now      = datetime.now(timezone.utc)
    expires  = now + timedelta(hours=JWT_EXPIRE_HOURS)

    payload = {
        "sub": user_id,
        "jti": token_id,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

    with get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token_id, user_id, created_at, expires_at) VALUES (?,?,?,?)",
            (token_id, user_id, now.isoformat(), expires.isoformat())
        )
        conn.execute(
            "UPDATE users SET last_login=? WHERE id=?",
            (now.isoformat(), user_id)
        )

    return token


def validate_session(token: str) -> dict | None:
    """Validate JWT and return user dict, or None if invalid/expired."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE token_id=? AND user_id=?",
            (payload["jti"], payload["sub"])
        ).fetchone()
    if not row:
        return None

    return get_user_by_id(payload["sub"])


def revoke_session(token: str):
    """Invalidate a session (logout or idle expiry)."""
    try:
        payload = jwt.decode(
            token, JWT_SECRET, algorithms=[JWT_ALGO],
            options={"verify_exp": False}
        )
        with get_db() as conn:
            conn.execute(
                "DELETE FROM sessions WHERE token_id=?",
                (payload["jti"],)
            )
    except Exception:
        pass


def revoke_all_sessions(user_id: str):
    """Revoke every active session for a user (e.g. password change)."""
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))

# ── Per-user data paths ───────────────────────────────────────────────────────

def user_data_path(user_id: str, subdir: str = "") -> Path:
    """Return the isolated data directory for this user. Never escapes DATA_ROOT."""
    base = (DATA_ROOT / user_id).resolve()
    if not str(base).startswith(str(DATA_ROOT.resolve())):
        raise PermissionError("Invalid user_id — path traversal attempt blocked.")
    path = (base / subdir).resolve() if subdir else base
    path.mkdir(parents=True, exist_ok=True)
    return path
