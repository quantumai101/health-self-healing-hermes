"""
auth/db_persistence.py — Persist users.db to HF Dataset across rebuilds.
"""
import os
import shutil
from pathlib import Path
from huggingface_hub import HfApi, hf_hub_download

REPO_ID  = "aiq00479/health-hermes-db"
DB_FILE  = "users.db"
DB_PATH  = Path(__file__).parent / DB_FILE   # → auth/users.db
TOKEN    = os.environ.get("HF_TOKEN")

def download_db():
    """Pull users.db from HF Dataset on container startup."""
    if not TOKEN:
        print("⚠️ HF_TOKEN not set — skipping DB restore")
        return
    try:
        path = hf_hub_download(
            repo_id=REPO_ID,
            filename=DB_FILE,
            repo_type="dataset",
            token=TOKEN
        )
        shutil.copy(path, DB_PATH)
        print("✅ users.db restored from HF Dataset")
    except Exception as e:
        print(f"⚠️ No existing DB on HF (first run?): {e}")

def upload_db():
    """Push users.db to HF Dataset after every write."""
    if not TOKEN:
        return
    try:
        api = HfApi()
        api.upload_file(
            path_or_fileobj=str(DB_PATH),
            path_in_repo=DB_FILE,
            repo_id=REPO_ID,
            repo_type="dataset",
            token=TOKEN
        )
        print("✅ users.db saved to HF Dataset")
    except Exception as e:
        print(f"❌ DB upload failed: {e}")