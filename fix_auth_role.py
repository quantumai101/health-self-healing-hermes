"""
fix_auth_role.py -- One-shot script to patch auth/auth.py with role column support.
Run from project root: python fix_auth_role.py
"""
import re, sys, subprocess
from pathlib import Path

AUTH = Path("auth/auth.py")

if not AUTH.exists():
    print(f"ERROR: {AUTH} not found. Run from project root.")
    sys.exit(1)

src = AUTH.read_text(encoding="utf-8")

# Check if already patched
if "role column" in src or "AUTO-PROMOTE" in src:
    print("INFO: auth.py already patched. Nothing to do.")
    sys.exit(0)

# Find and replace the init_db executescript block
OLD = '''        conn.executescript("""
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
    DATA_ROOT.mkdir(parents=True, exist_ok=True)'''

NEW = '''        conn.executescript("""
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

        # Add role column if upgrading existing DB (safe to run multiple times)
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            conn.commit()
        except Exception:
            pass  # role column already exists

        # AUTO-PROMOTE: ensure this account is always admin
        conn.execute("""
            UPDATE users SET role='admin'
            WHERE email='aiq00479@gmail.com'
            AND (role IS NULL OR role != 'admin')
        """)
        conn.commit()

    DATA_ROOT.mkdir(parents=True, exist_ok=True)'''

if OLD in src:
    patched = src.replace(OLD, NEW)
    AUTH.write_text(patched, encoding="utf-8")
    print("OK: auth.py patched with role column + admin auto-promote.")
else:
    # Try looser match -- find executescript block
    print("WARN: Exact block not matched. Trying to insert after executescript...")
    # Insert the ALTER TABLE + UPDATE after the executescript closing
    insert_after = '        """)\n    DATA_ROOT.mkdir'
    replacement = '        """)\n\n        # Add role column if upgrading existing DB\n        try:\n            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT \'user\'")\n            conn.commit()\n        except Exception:\n            pass\n\n        # AUTO-PROMOTE admin\n        conn.execute("""\n            UPDATE users SET role=\'admin\'\n            WHERE email=\'aiq00479@gmail.com\'\n            AND (role IS NULL OR role != \'admin\')\n        """)\n        conn.commit()\n\n    DATA_ROOT.mkdir'
    if insert_after in src:
        patched = src.replace(insert_after, replacement)
        AUTH.write_text(patched, encoding="utf-8")
        print("OK: auth.py patched via fallback method.")
    else:
        print("ERROR: Could not locate insertion point in auth.py.")
        print("Please manually edit auth/auth.py -- add after executescript block:")
        print("""
        try:
            conn.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
            conn.commit()
        except Exception:
            pass
        conn.execute(\"\"\"
            UPDATE users SET role='admin'
            WHERE email='aiq00479@gmail.com'
        \"\"\")
        conn.commit()
""")
        sys.exit(1)

# Git push
print("Pushing to git...")
subprocess.run(["git", "add", "auth/auth.py"], check=True)
subprocess.run(["git", "commit", "-m", "fix: add role column and auto-promote admin"], check=True)
subprocess.run(["git", "push", "huggingface", "main"], check=True)
subprocess.run(["git", "push", "origin", "main"], check=True)
print("DONE: Pushed to both remotes. Wait 60s for HF rebuild, then logout and login.")
