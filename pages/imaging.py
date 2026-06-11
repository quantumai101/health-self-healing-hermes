import streamlit as st
import hashlib
import logging
import os
import tempfile
import shutil
import uuid
import time
from typing import Dict, Any, Optional, Generator
from contextlib import contextmanager
from pathlib import Path
import pydicom
from pydicom.errors import InvalidDicomError
from pydicom.dataset import Dataset
import numpy as np
from dicom_anonymizer import anonymize_dataset

# ---------------------------------------------------------------------------
# LOGGING & CONFIGURATION
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MediSync.Imaging")

ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/bmp', 
    'image/tiff', 'application/dicom'
}
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff', '.dcm', '.dicom'}
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
SESSION_TIMEOUT_SECONDS = 3600

# ---------------------------------------------------------------------------
# SESSION & STORAGE MANAGEMENT
# ---------------------------------------------------------------------------

@contextmanager
def secure_temp_file(suffix: str = ".tmp") -> Generator[Path, None, None]:
    """
    Context manager for secure temporary file handling.
    Ensures file deletion upon exit, preventing orphaned PHI data.
    """
    tmp_dir = get_session_dir()
    tmp_path = Path(tmp_dir) / f"{uuid.uuid4()}{suffix}"
    try:
        yield tmp_path
    finally:
        if tmp_path.exists():
            os.remove(tmp_path)
            logger.info(f"Audit: Securely deleted temporary file: {tmp_path}")

def get_session_dir():
    """
    Returns a secure, isolated directory for the current session.
    Uses a unique directory per session to prevent race conditions.
    """
    if "user_temp_dir" not in st.session_state:
        tmp_dir = tempfile.mkdtemp(prefix='medisync_')
        os.chmod(tmp_dir, 0o700)
        st.session_state.user_temp_dir = tmp_dir
        st.session_state.last_accessed = time.time()
        logger.info(f"Created secure session directory: {tmp_dir}")
    
    if time.time() - st.session_state.get("last_accessed", 0) > SESSION_TIMEOUT_SECONDS:
        cleanup_session_dir()
        return get_session_dir()
        
    st.session_state.last_accessed = time.time()
    return st.session_state.user_temp_dir

def cleanup_session_dir():
    """Purges session-specific temporary files and clears state."""
    path = st.session_state.get("user_temp_dir")
    if path and os.path.exists(path):
        try:
            shutil.rmtree(path)
            logger.info(f"Audit: Cleaned up session directory: {path}")
        except Exception as e:
            logger.error(f"Failed to cleanup session directory: {e}")
    
    for key in ["user_temp_dir", "uploaded_files", "processed_files", "last_accessed"]:
        if key in st.session_state:
            del st.session_state[key]

# ---------------------------------------------------------------------------
# CLINICAL SAFETY & DICOM PROCESSING
# ---------------------------------------------------------------------------
def scrub_phi(ds: Dataset) -> None:
    """
    Clinical Safety: Uses dicom-anonymizer to perform robust de-identification.
    Complies with DICOM PS3.15 Annex E.
    """
    try:
        anonymize_dataset(ds, remove_private_tags=True)
        logger.info("Applied robust DICOM-Anonymizer profile.")
    except Exception as e:
        logger.error(f"Anonymization failed: {e}")
        raise

def validate_and_scrub_dicom(file_path: str) -> bool:
    """
    Performs deep inspection and PHI scrubbing.
    NOTE: Automated burned-in text detection is not implemented. 
    All DICOM uploads are flagged for manual clinical review.
    """
    try:
        ds = pydicom.dcmread(file_path)
        scrub_phi(ds)
        ds.save_as(file_path, write_like_original=False)
        logger.info(f"Audit: DICOM file processed and scrubbed: {file_path}")
        return True
    except (InvalidDicomError, Exception) as e:
        logger.error(f"DICOM processing failed: {e}")
        return False

def process_file_stream(uploaded_file) -> Optional[Dict[str, Any]]:
    """Processes file with strict validation and audit logging."""
    try:
        if uploaded_file.size > MAX_FILE_SIZE_BYTES:
            return None

        # Validate extension
        ext = Path(uploaded_file.name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return None

        sha256 = hashlib.sha256()
        for chunk in iter(lambda: uploaded_file.read(4096), b""):
            sha256.update(chunk)
        file_hash = sha256.hexdigest()
        uploaded_file.seek(0)

        if "processed_files" not in st.session_state:
            st.session_state.processed_files = {}
        
        if file_hash in st.session_state.processed_files:
            return st.session_state.processed_files[file_hash]

        # mime check via extension only (no python-magic dependency on HF)
        ext_to_mime = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
            '.png': 'image/png',  '.webp': 'image/webp',
            '.bmp': 'image/bmp',  '.tiff': 'image/tiff',
            '.dcm': 'application/dicom', '.dicom': 'application/dicom',
        }
        mime = ext_to_mime.get(ext, 'application/octet-stream')
        if mime not in ALLOWED_MIME_TYPES:
            return None
            
        with secure_temp_file(suffix=ext) as tmp_path:
            with open(tmp_path, "wb") as f:
                for chunk in iter(lambda: uploaded_file.read(8192), b""):
                    f.write(chunk)
            
            os.chmod(tmp_path, 0o600)
            
            if mime == 'application/dicom':
                if not validate_and_scrub_dicom(str(tmp_path)):
                    return None

            # Copy to a persistent location for the session duration
            final_path = Path(get_session_dir()) / f"{uuid.uuid4()}{ext}"
            shutil.copy2(tmp_path, final_path)
            
            result = {"name": uploaded_file.name, "hash": file_hash, "path": str(final_path), "manual_review": True}
            st.session_state.processed_files[file_hash] = result
            return result
    except Exception as e:
        logger.error(f"Processing failed: {str(e)}")
        return None

# ---------------------------------------------------------------------------
# UI & MAIN
# ---------------------------------------------------------------------------
def inject_ui_assets():
    st.markdown("""
    <style>
    section[data-testid="stFileUploaderDropzone"] { border: 2px dashed #2a2a4a !important; border-radius: 14px !important; }
    </style>
    """, unsafe_allow_html=True)

def render():
    """Entry point for app.py routing."""
    _render_inner()


def _render_inner():
    st.set_page_config(page_title="MediSync Imaging", layout="wide")
    inject_ui_assets()

    st.title("🩻 Medical Imaging Analysis")
    
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}

    uploaded_files = st.file_uploader("Upload scans", accept_multiple_files=True)

    if uploaded_files:
        for f in uploaded_files:
            validated_data = process_file_stream(f)
            if validated_data:
                st.session_state.uploaded_files[validated_data["hash"]] = validated_data
            else:
                st.error(f"Invalid, unsupported, or oversized file: {f.name}")

    if st.button("Clear All Scans", key="imaging_clear_all_scans_btn"):
        cleanup_session_dir()
        st.rerun()

    if st.session_state.get("uploaded_files"):
        st.write("### Queued Scans")
        for file_meta in st.session_state.uploaded_files.values():
            st.info(f"Processed: {file_meta['name']} - ⚠️ MANUAL REVIEW REQUIRED")

    st.sidebar.markdown("### ⚠️ Clinical Disclaimer\nFindings must be verified by a clinician. AI output is for research/support only. All DICOM files require manual review for burned-in PHI.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Uncaught error: {str(e)}", exc_info=True)
        st.error("A critical error occurred.")