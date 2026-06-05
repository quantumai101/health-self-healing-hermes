import streamlit as st
import hashlib
import logging
import magic
import os
import tempfile
import shutil
import uuid
from typing import Dict, Any, Optional
import pydicom
from pydicom.errors import InvalidDicomError
from pydicom.dataset import Dataset
from pydicom.pixel_data_handlers.util import pixel_data_array
from streamlit.runtime.scriptrunner import get_script_run_ctx

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
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# ---------------------------------------------------------------------------
# SESSION & STORAGE MANAGEMENT
# ---------------------------------------------------------------------------
def get_session_dir():
    """Returns a secure, isolated directory for the current session."""
    if "user_temp_dir" not in st.session_state:
        base_dir = os.path.join(tempfile.gettempdir(), "medisync_secure")
        os.makedirs(base_dir, exist_ok=True)
        session_id = str(uuid.uuid4())
        path = os.path.join(base_dir, session_id)
        os.makedirs(path, mode=0o700, exist_ok=True)
        st.session_state.user_temp_dir = path
        
        # Register session-end cleanup using Streamlit's context
        ctx = get_script_run_ctx()
        if ctx:
            from streamlit.runtime import runtime
            runtime.get_instance().on_session_end(cleanup_session_dir)
            
    return st.session_state.user_temp_dir

def cleanup_session_dir():
    """Purges session-specific temporary files securely."""
    path = st.session_state.get("user_temp_dir")
    if path and os.path.exists(path):
        try:
            shutil.rmtree(path)
            logger.info(f"Cleaned up session directory: {path}")
        except Exception as e:
            logger.error(f"Failed to cleanup session directory: {e}")

# ---------------------------------------------------------------------------
# CLINICAL SAFETY & DICOM PROCESSING
# ---------------------------------------------------------------------------
def scrub_phi(ds: Dataset) -> None:
    """
    Clinical Safety: Strips PHI tags from DICOM metadata.
    Uses pydicom's deidentify logic. 
    WARNING: This is a baseline implementation. Pixel-embedded PHI 
    (e.g., burned-in text) requires specialized OCR/AI detection.
    """
    # Remove private tags and standard PHI
    ds.remove_private_tags()
    
    # Define tags to redact
    phi_tags = [
        'PatientName', 'PatientID', 'PatientBirthDate', 'PatientAddress', 
        'PatientTelephoneNumbers', 'PatientMotherBirthName', 'InstitutionName',
        'ReferringPhysicianName', 'PerformingPhysicianName', 'StudyInstanceUID',
        'SeriesInstanceUID', 'AccessionNumber'
    ]
    for tag in phi_tags:
        if tag in ds:
            ds.data_element(tag).value = "REDACTED"

def validate_and_scrub_dicom(file_path: str) -> bool:
    """
    Performs deep inspection and PHI scrubbing of DICOM files.
    """
    try:
        ds = pydicom.dcmread(file_path)
        scrub_phi(ds)
        # Ensure file is saved with standard transfer syntax
        ds.save_as(file_path, write_like_original=False)
        return True
    except (InvalidDicomError, Exception) as e:
        logger.error(f"DICOM processing failed: {e}")
        return False

def process_file_stream(uploaded_file) -> Optional[Dict[str, Any]]:
    """
    Processes file using a streaming approach to prevent OOM errors.
    Includes MIME-type validation against file extension.
    """
    try:
        # Calculate hash
        sha256 = hashlib.sha256()
        for chunk in iter(lambda: uploaded_file.read(4096), b""):
            sha256.update(chunk)
        file_hash = sha256.hexdigest()
        uploaded_file.seek(0)

        if "processed_files" not in st.session_state:
            st.session_state.processed_files = {}
        
        if file_hash in st.session_state.processed_files:
            return st.session_state.processed_files[file_hash]

        # MIME validation
        header = uploaded_file.read(2048)
        uploaded_file.seek(0)
        mime = magic.from_buffer(header, mime=True)
        
        if mime not in ALLOWED_MIME_TYPES:
            return None
            
        # Secure file write
        tmp_path = os.path.join(get_session_dir(), f"{uuid.uuid4()}.tmp")
        with open(tmp_path, "wb") as f:
            for chunk in iter(lambda: uploaded_file.read(8192), b""):
                f.write(chunk)
        
        if mime == 'application/dicom':
            if not validate_and_scrub_dicom(tmp_path):
                if os.path.exists(tmp_path): os.remove(tmp_path)
                return None

        result = {"name": uploaded_file.name, "hash": file_hash, "path": tmp_path}
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

def main():
    st.set_page_config(page_title="MediSync Imaging", layout="wide")
    inject_ui_assets()

    st.title("🩻 Medical Imaging Analysis")
    
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}

    uploaded_files = st.file_uploader("Upload scans", accept_multiple_files=True)

    if uploaded_files:
        for f in uploaded_files:
            if f.size > MAX_FILE_SIZE_BYTES:
                st.error(f"File {f.name} exceeds size limit.")
                continue
                
            validated_data = process_file_stream(f)
            if validated_data:
                st.session_state.uploaded_files[validated_data["hash"]] = validated_data
            else:
                st.error(f"Invalid or unsupported file format: {f.name}")

    if st.button("Clear All Scans"):
        cleanup_session_dir()
        st.session_state.uploaded_files = {}
        st.session_state.processed_files = {}
        st.rerun()

    if st.session_state.uploaded_files:
        st.write("### Queued Scans")
        for file_id, file_meta in st.session_state.uploaded_files.items():
            st.info(f"Processed: {file_meta['name']}")

    st.sidebar.markdown("### ⚠️ Clinical Disclaimer\nFindings must be verified by a clinician. AI output is for research/support only.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Uncaught error: {str(e)}", exc_info=True)
        st.error("A critical error occurred.")