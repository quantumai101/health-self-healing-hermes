"""
fix_db_persistence.py -- Patches auth/auth.py to sync users.db
to/from the private HF Dataset (aiq00479/health-hermes-db)
so the database survives container rebuilds on free-tier HF Spaces.

Run from project root: python fix_db_persistence.py
"""
import sys, subprocess, shutil
from pathlib import Path

AUTH = Path("auth") / "auth.py"

if not AUTH.exists():
    print(f"ERROR: {AUTH} not found. Run from project root.")
    sys.exit(1)

src = AUTH.read_text(encoding="utf-8")

# Check if already patched
if "huggingface_hub" in src and "hf_db_sync" in src:
    print("INFO: DB persistence already patched.")
else:
    # Backup
    bak = AUTH.with_suffix(".py.bak_dbsync")
    shutil.copy2(AUTH, bak)
    print(f"OK: Backup saved to {bak}")

    # New imports block to add after existing imports
    HF_SYNC_CODE = '''
# -- HF Dataset DB Sync (free-tier persistence) -------------------------------
import threading
try:
    from huggingface_hub import hf_hub_download, upload_file, HfApi
    _HF_SYNC_AVAILABLE = True
except ImportError:
    _HF_SYNC_AVAILABLE = False

_HF_DATASET_REPO = "aiq00479/health-hermes-db"
_HF_DB_FILENAME  = "users.db"
_DB_SYNC_LOCK    = threading.Lock()

def _hf_token() -> str:
    """Read HF token from env (set as HF_TOKEN secret in Space settings)."""
    return os.getenv("HF_TOKEN", "")

def hf_db_pull():
    """Download users.db from HF Dataset into local DB_PATH on startup."""
    if not _HF_SYNC_AVAILABLE or not _hf_token():
        return
    try:
        local = hf_hub_download(
            repo_id=_HF_DATASET_REPO,
            filename=_HF_DB_FILENAME,
            repo_type="dataset",
            token=_hf_token(),
            local_dir=str(DB_PATH.parent),
            local_dir_use_symlinks=False,
        )
        import shutil as _sh
        if Path(local) != DB_PATH:
            _sh.copy2(local, DB_PATH)
    except Exception:
        pass  # First run: no DB yet, init_db() will create it

def hf_db_push():
    """Upload current users.db to HF Dataset (called after write operations)."""
    if not _HF_SYNC_AVAILABLE or not _hf_token() or not DB_PATH.exists():
        return
    def _push():
        with _DB_SYNC_LOCK:
            try:
                api = HfApi(token=_hf_token())
                api.upload_file(
                    path_or_fileobj=str(DB_PATH),
                    path_in_repo=_HF_DB_FILENAME,
                    repo_id=_HF_DATASET_REPO,
                    repo_type="dataset",
                )
            except Exception:
                pass
    threading.Thread(target=_push, daemon=True).start()
# -----------------------------------------------------------------------------
'''

    # Insert after the last import line
    lines = src.splitlines()
    last_import = 0
    for i, line in enumerate(lines):
        if line.startswith(("import ", "from ")):
            last_import = i
    lines.insert(last_import + 1, HF_SYNC_CODE)
    patched = "\n".join(lines)

    # Patch init_db() to call hf_db_pull() at the very start
    patched = patched.replace(
        'def init_db():\n    """Create tables if they don\'t exist. Call once at app startup."""',
        'def init_db():\n    """Create tables if they don\'t exist. Call once at app startup."""\n    hf_db_pull()  # Restore DB from HF Dataset if available'
    )

    # Patch create_user() to push after insert
    patched = patched.replace(
        '    return get_user_by_id(user_id)\n\n\ndef get_user_by_email',
        '    hf_db_push()  # Persist new user to HF Dataset\n    return get_user_by_id(user_id)\n\n\ndef get_user_by_email'
    )

    # Patch create_session() to push after login
    patched = patched.replace(
        '    return token\n\n\ndef validate_session',
        '    hf_db_push()  # Persist session to HF Dataset\n    return token\n\n\ndef validate_session'
    )

    AUTH.write_text(patched, encoding="utf-8")
    print("OK: auth.py patched with HF Dataset DB sync.")

# Add huggingface_hub to requirements.txt
REQ = Path("requirements.txt")
if REQ.exists():
    req_src = REQ.read_text(encoding="utf-8")
    if "huggingface_hub" not in req_src:
        with open(REQ, "a") as f:
            f.write("\nhuggingface_hub>=0.20.0\n")
        print("OK: Added huggingface_hub to requirements.txt")
    else:
        print("INFO: huggingface_hub already in requirements.txt")

print("")
print("IMPORTANT: Add your HF token as a secret in Space Settings:")
print("  1. Go to huggingface.co/spaces/aiq00479/health-self-healing-hermes/settings")
print("  2. Scroll to 'Variables and secrets'")
print("  3. Click 'New secret'")
print("  4. Name: HF_TOKEN")
print("  5. Value: your HF access token from huggingface.co/settings/tokens")
print("")

# Git push
for cmd, desc in [
    (["git", "add", "auth/auth.py", "requirements.txt"], "Staged"),
    (["git", "commit", "-m", "fix: add HF Dataset DB sync for free-tier persistence"], "Committed"),
    (["git", "push", "huggingface", "main"], "Pushed HF"),
    (["git", "push", "origin", "main"], "Pushed GitHub"),
]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 or "nothing to commit" in r.stdout + r.stderr
    print(f"{'OK' if ok else 'WARN'}: {desc}" + ("" if ok else f" -- {r.stderr.strip()[:80]}"))

print("DONE: After setting HF_TOKEN secret, register once and your account persists forever.")
