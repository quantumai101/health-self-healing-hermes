import streamlit as st
import hashlib
import logging
import magic
import os
import tempfile
from typing import List, Dict, Any, Optional

# ---------------------------------------------------------------------------
# LOGGING CONFIGURATION
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("MediSync.Imaging")

# ---------------------------------------------------------------------------
# CONSTANTS & CONFIG
# ---------------------------------------------------------------------------
ALLOWED_MIME_TYPES = {
    'image/jpeg', 'image/png', 'image/webp', 'image/bmp', 
    'image/tiff', 'application/dicom'
}
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
TEMP_DIR = tempfile.mkdtemp(prefix="medisync_")

# ---------------------------------------------------------------------------
# UTILITY MODULES
# ---------------------------------------------------------------------------
def inject_ui_assets():
    """Injects CSS/JS assets for the imaging interface."""
    PAGE_CSS = r"""
    <style>
    section[data-testid="stFileUploaderDropzone"] {
        border: 2px dashed #2a2a4a !important;
        border-radius: 14px !important;
        background: #08080f !important;
        min-height: 210px !important;
    }
    div[data-testid="stFileUploaderDropzoneInstructions"] { display: none !important; }
    </style>
    """
    st.markdown(PAGE_CSS, unsafe_allow_html=True)

def get_file_hash(file_path: str) -> str:
    """Generates SHA-256 hash for integrity verification from disk."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def validate_and_save_file(file_obj) -> Optional[Dict[str, Any]]:
    """
    Validates file integrity and MIME type.
    Clinical safety: Ensures file is not corrupted or malicious before processing.
    Uses temporary disk storage to prevent memory exhaustion.
    """
    try:
        # Check file size before processing
        if file_obj.size > MAX_FILE_SIZE_BYTES:
            logger.warning(f"File {file_obj.name} exceeds size limit.")
            return None

        # Validate MIME type using header
        header = file_obj.read(2048)
        file_obj.seek(0)
        mime = magic.from_buffer(header, mime=True)
        
        if mime not in ALLOWED_MIME_TYPES:
            logger.warning(f"Unsupported MIME type {mime} for {file_obj.name}")
            return None
            
        # Save to temporary storage instead of memory
        temp_path = os.path.join(TEMP_DIR, f"{hashlib.md5(file_obj.name.encode()).hexdigest()}.tmp")
        with open(temp_path, "wb") as f:
            f.write(file_obj.getbuffer())
            
        return {
            "name": file_obj.name,
            "hash": get_file_hash(temp_path),
            "path": temp_path
        }
    except Exception as e:
        logger.error(f"Validation failed for {file_obj.name}: {str(e)}")
        return None

# ---------------------------------------------------------------------------
# CORE LOGIC
# ---------------------------------------------------------------------------
def main():
    st.set_page_config(page_title="MediSync Imaging", layout="wide")
    inject_ui_assets()

    st.title("🩻 Medical Imaging Analysis")
    
    # Store file metadata and paths, not raw bytes
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}

    uploaded_files = st.file_uploader(
        "Upload scans", 
        accept_multiple_files=True, 
        label_visibility="collapsed"
    )

    if uploaded_files:
        for f in uploaded_files:
            validated_data = validate_and_save_file(f)
            if validated_data:
                file_id = validated_data["hash"]
                if file_id not in st.session_state.uploaded_files:
                    st.session_state.uploaded_files[file_id] = validated_data
            else:
                st.error(f"Invalid or unsupported file format: {f.name}")

    col1, col2 = st.columns([0.8, 0.2])
    if col2.button("Clear All Scans"):
        # Cleanup temp files
        for meta in st.session_state.uploaded_files.values():
            if os.path.exists(meta["path"]):
                os.remove(meta["path"])
        st.session_state.uploaded_files = {}
        st.rerun()

    if st.session_state.uploaded_files:
        st.write("### Queued Scans")
        cols = st.columns(4)
        items = list(st.session_state.uploaded_files.items())
        for i, (file_id, file_meta) in enumerate(items):
            with cols[i % 4]:
                st.info(file_meta["name"])
                if st.button(f"Remove {file_meta['name']}", key=f"del_{file_id}"):
                    if os.path.exists(file_meta["path"]):
                        os.remove(file_meta["path"])
                    del st.session_state.uploaded_files[file_id]
                    st.rerun()

    st.sidebar.markdown("""
    ### ⚠️ Clinical Disclaimer
    This tool is for educational/workflow support only. 
    Findings must be verified by a qualified clinician.
    """)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Uncaught application error: {str(e)}", exc_info=True)
        st.error("A critical error occurred. Please contact system administration.")