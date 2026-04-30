"""
core/db.py
DuckDB connection and schema management.
All database operations go through this module.
"""

import os
import shutil
import duckdb
import streamlit as st
from core.config import DB_PATH, REPO_ID
from core.session import add_log


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection, creating the DB file if needed."""
    conn = duckdb.connect(DB_PATH)
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    """Create tables if they don't exist. Safe to call multiple times."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS patient_health_records (
            patient_id            VARCHAR PRIMARY KEY,
            age_years             INTEGER,
            bmi                   DOUBLE,
            bmi_band              VARCHAR,
            disease_risk          VARCHAR,
            risk_score            DOUBLE,
            status                VARCHAR,
            region                VARCHAR,
            in_high_risk_zone     VARCHAR,
            patients_affected     INTEGER,
            systolic_bp           INTEGER,
            fasting_glucose_mmol  DOUBLE,
            hba1c_pct             DOUBLE,
            last_review_date      VARCHAR,
            ingested_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ehr_summaries (
            summary_id    VARCHAR PRIMARY KEY,
            patient_id    VARCHAR,
            filename      VARCHAR,
            raw_text      TEXT,
            ai_summary    TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS imaging_reports (
            report_id     VARCHAR PRIMARY KEY,
            patient_id    VARCHAR,
            filename      VARCHAR,
            image_meta    VARCHAR,
            ai_report     TEXT,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def load_synthetic_data() -> bool:
    """Load synthetic patient data into DB if table is empty. Returns True on success."""
    try:
        conn = get_connection()
        count = conn.execute("SELECT COUNT(*) FROM patient_health_records").fetchone()[0]
        if count == 0:
            from data.synthetic_patients import generate_patients
            df = generate_patients()
            conn.execute("INSERT INTO patient_health_records SELECT * FROM df")
            add_log(f"DB_LOADED:{len(df)} synthetic records")
        conn.close()
        return True
    except Exception as e:
        add_log(f"DB_ERR:{str(e)[:30]}")
        return False


def get_all_patients():
    """Return all patient records as a pandas DataFrame."""
    try:
        conn = get_connection()
        df = conn.execute("SELECT * FROM patient_health_records").df()
        conn.close()
        return df
    except Exception as e:
        add_log(f"DB_QUERY_ERR:{str(e)[:30]}")
        return None


def sync_from_hf() -> None:
    """Download DB backup from HuggingFace dataset repo."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        add_log("SYNC_NO_TOKEN"); return
    try:
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(
            repo_id=REPO_ID, filename="health.duckdb",
            repo_type="dataset", token=token
        )
        shutil.copyfile(path, DB_PATH)
        add_log("HF_SYNC_OK")
    except Exception as e:
        add_log(f"HF_SYNC_ERR:{str(e)[:25]}")


def backup_to_hf() -> None:
    """Upload local DB to HuggingFace dataset repo."""
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        add_log("BACKUP_NO_TOKEN"); return
    if not os.path.exists(DB_PATH):
        add_log("BACKUP_NO_DB"); return
    try:
        from huggingface_hub import HfApi
        HfApi().upload_file(
            path_or_fileobj=DB_PATH, path_in_repo="health.duckdb",
            repo_id=REPO_ID, repo_type="dataset", token=token
        )
        add_log("HF_BACKUP_OK")
    except Exception as e:
        add_log(f"HF_BACKUP_ERR:{str(e)[:25]}")
