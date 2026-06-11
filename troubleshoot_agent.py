"""
troubleshoot_agent.py — Production Autonomous Self-Healing & Verification Agent
================================================================================
Monitors runtime interface errors and self-heals DuplicateWidgetID exceptions
via local Ollama codex-app daemon.

SAFETY FIXES (2026-06-11):
  - IdentitySchemaManager NO LONGER wipes totp_secret / mfa_enabled.
    It only creates tables and ensures the user row exists.
    This prevents MS Authenticator entries from being invalidated.
  - DB sync is skipped entirely if the database already has a valid
    totp_secret for the admin account (MFA already configured).
  - Added PROTECTED_DATABASES list to block writes to HF /data/ paths.
  - LocalCodexDaemonEngine now has a PROTECTED_FILES list preventing
    rewrites of auth/, pages/login.py, core/config.py.
"""

import os
import sys
import time
import subprocess
import logging
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("HermesOrchestrator")
audit_log = logging.getLogger("TroubleshootAudit")

# ---------------------------------------------------------------------------
# PROTECTED FILES — never rewritten by the self-healing engine
# ---------------------------------------------------------------------------
PROTECTED_FILES = {
    "auth/auth.py",
    "auth/session.py",
    "auth/db_persistence.py",
    "auth/__init__.py",
    "pages/login.py",
    "core/config.py",
    "troubleshoot_agent.py",
}

# ---------------------------------------------------------------------------
# PROTECTED DB PATHS — never modified by IdentitySchemaManager
# ---------------------------------------------------------------------------
PROTECTED_DB_PATTERNS = [
    "/data/",           # HF Spaces persistent storage
    "huggingface",      # any HF path
]


class LocalCodexDaemonEngine:
    """Manages communication with the local Ollama codex-app daemon."""

    def __init__(self, script_target: Path):
        self.script_target = script_target

    def _is_protected(self) -> bool:
        """Returns True if this file must never be rewritten."""
        rel = str(self.script_target)
        for protected in PROTECTED_FILES:
            if rel.endswith(protected.replace("/", os.sep)):
                return True
        return False

    def dispatch_self_healing_transaction(self, diagnostic_traceback: str) -> bool:
        if self._is_protected():
            logger.warning(
                f"🛡️  PROTECTED FILE — skipping rewrite: {self.script_target.name}. "
                "Edit manually if needed."
            )
            return False

        logger.info(
            f"🤖 Packaging exception context. "
            f"Querying Codex App to optimize: {self.script_target.name}"
        )

        reconstruction_prompt = f"""
You are an expert MLOps core engineer running inside an automated verification loop.
The script `{self.script_target.name}` encountered a runtime failure or layout conflict.

Rewrite the ENTIRE script completely from scratch.
CONSTRAINTS:
1. Retain the autonomous recovery framework including test_headless_runtime_state and os.execv hot-swap.
2. Resolve component key conflicts described in the traceback below.
3. Use --server.headless true for all background Streamlit commands.
4. Spell out all database initialisations explicitly — no placeholder comments.
5. NEVER modify auth/, pages/login.py, or core/config.py.

Current file content:
{self.script_target.read_text(encoding='utf-8') if self.script_target.exists() else '# New script'}

Traceback:
{diagnostic_traceback}

Respond ONLY with valid executable Python. No markdown outside the code block.
"""
        try:
            result = subprocess.run(
                ["ollama", "run", "codex-app", reconstruction_prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
            code = result.stdout.strip()

            if code.startswith("```python"):
                code = code.split("```python")[1].split("```")[0].strip()
            elif code.startswith("```"):
                code = code.split("```")[1].split("```")[0].strip()

            if len(code) > 2000:
                self.script_target.write_text(code, encoding="utf-8")
                logger.info(f"✨ {self.script_target.name} updated. Length: {len(code)}")
                audit_log.info(f"Commit written: {len(code)} chars")
                return True
            else:
                logger.error("❌ Output too short — overwrite blocked (truncated payload).")
                return False

        except Exception as e:
            logger.error(f"❌ Codex App communication error: {e}")
            return False


def test_headless_runtime_state() -> str:
    """
    Launches a headless Streamlit instance and checks for DuplicateWidgetID errors.
    Returns 'OK' if clean, otherwise returns the captured error log.
    """
    logger.info("🧪 Scanning workspace views for DuplicateWidgetIDs...")
    try:
        run = subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "app.py",
             "--server.headless", "true"],
            capture_output=True,
            text=True,
            timeout=12,
        )
        combined = run.stdout + "\n" + run.stderr
        if "DuplicateWidgetID" in combined or "Error" in combined:
            return combined
        return "OK"

    except subprocess.TimeoutExpired as e:
        stdout = e.stdout.decode("utf-8", errors="ignore") if e.stdout else ""
        stderr = e.stderr.decode("utf-8", errors="ignore") if e.stderr else ""
        captured = stdout + "\n" + stderr
        if "DuplicateWidgetID" in captured or "No such option" in captured:
            return captured
        return "OK"


class IdentitySchemaManager:
    """
    Safely ensures the SQLite schema exists.

    SAFE VERSION — does NOT wipe totp_secret, mfa_enabled, or backup_codes.
    Only creates tables and inserts a fallback user row if one does not exist.
    This means MS Authenticator entries remain valid after every run.
    """

    @staticmethod
    def _is_protected_db(db_path: Path) -> bool:
        path_str = str(db_path).replace("\\", "/")
        for pattern in PROTECTED_DB_PATTERNS:
            if pattern in path_str:
                return True
        return False

    @staticmethod
    def synchronize_local_user_tables(
        database_file_path: Path, administrative_email: str
    ) -> bool:
        # Block writes to HF persistent storage or any protected path
        if IdentitySchemaManager._is_protected_db(database_file_path):
            logger.warning(
                f"🛡️  PROTECTED DB — skipping sync: {database_file_path}. "
                "Never wipe production MFA secrets."
            )
            return False

        try:
            conn = sqlite3.connect(database_file_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            # Create tables only — never alter existing data
            cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id              TEXT PRIMARY KEY,
                email           TEXT UNIQUE NOT NULL,
                name            TEXT NOT NULL,
                password_hash   TEXT NOT NULL,
                totp_secret     TEXT,
                mfa_enabled     INTEGER DEFAULT 0,
                backup_codes    TEXT,
                role            TEXT DEFAULT 'user',
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
            conn.commit()

            # Check if user already exists WITH a valid totp_secret
            existing = cur.execute(
                "SELECT id, totp_secret, mfa_enabled FROM users WHERE email = ?",
                (administrative_email,),
            ).fetchone()

            if existing and existing["totp_secret"]:
                # MFA already configured — do NOT touch this row
                logger.info(
                    f"✅ MFA configured for {administrative_email} — "
                    "skipping DB reset to preserve Authenticator entry."
                )
                conn.close()
                return True

            if not existing:
                # Insert a minimal fallback row only if user doesn't exist at all
                fallback_id = "usr_admin_fallback"
                timestamp = datetime.now(timezone.utc).isoformat()
                mock_hash = (
                    "$2b$12$eAui1D6/8R6vunI7f6X/9O"
                    "HV4.A7vM1X2C3d4e5f6g7h8i9j0k1l2"
                )
                cur.execute(
                    "INSERT OR IGNORE INTO users "
                    "(id, email, name, password_hash, created_at, role) "
                    "VALUES (?, ?, ?, ?, ?, 'admin')",
                    (fallback_id, administrative_email,
                     "Admin Core", mock_hash, timestamp),
                )
                conn.commit()
                logger.info(
                    f"✅ Fallback admin row created for {administrative_email}. "
                    "Complete MFA setup on first login."
                )
            else:
                # User exists but has no totp_secret yet — safe to set role only
                cur.execute(
                    "UPDATE users SET role = 'admin' WHERE email = ?",
                    (administrative_email,),
                )
                conn.commit()
                logger.info(
                    f"✅ Role confirmed admin for {administrative_email}. "
                    "MFA not yet set up — will be prompted on next login."
                )

            conn.close()
            return True

        except Exception as e:
            logger.error(f"❌ DB sync error for {database_file_path.name}: {e}")
            return False


def run_orchestrator_executive_loop():
    """Main execution loop — monitors and self-heals widget errors."""
    directory_root = Path(__file__).parent.resolve()
    active_script_path = Path(__file__).resolve()
    target_developer_account = "aiq00479@gmail.com"

    current_depth = int(os.environ.get("HERMES_LOOP_DEPTH", "0"))
    max_heals = 5

    print("\n" + "=" * 90)
    logger.info(
        f"🔄 Self-Healing Orchestration Run "
        f"({current_depth}/{max_heals})"
    )
    print("=" * 90)

    # Safe DB schema sync — never wipes MFA secrets
    for db_name in ["users.db", "auth/users.db"]:
        db_path = directory_root / db_name
        if db_path.parent.exists():
            IdentitySchemaManager.synchronize_local_user_tables(
                db_path, target_developer_account
            )

    # Headless validation
    result = test_headless_runtime_state()

    if "OK" in result:
        logger.info(
            "✅ Interface validation clean. All layout states stable."
        )
        os.environ["HERMES_LOOP_DEPTH"] = "0"
        return

    if current_depth >= max_heals:
        logger.error(
            "🚨 Max self-healing depth reached. "
            "Halting to protect local assets."
        )
        return

    logger.warning("⚠️ Widget ID collision or render error detected.")
    engine = LocalCodexDaemonEngine(script_target=active_script_path)
    success = engine.dispatch_self_healing_transaction(
        diagnostic_traceback=result
    )

    if success:
        logger.info("🚀 Hot-swapping patched process...")
        os.environ["HERMES_LOOP_DEPTH"] = str(current_depth + 1)
        time.sleep(1.2)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    else:
        logger.error("❌ Self-healing halted — Codex App unavailable.")


if __name__ == "__main__":
    run_orchestrator_executive_loop()
