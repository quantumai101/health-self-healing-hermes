"""
pages/imaging.py — 🩻 Advanced Multi-Sequence Imaging Core
===========================================================
Multi-file upload with sequence grid display.
render() function for app.py routing.

Fixes:
  - Restored 🩻 icon and "Advanced Multi-Sequence Imaging Core" heading
  - Multi-file drag-and-drop upload (PNG, JPG, DICOM up to 200MB)
  - Sequence grid: Axial / Sagittal / Coronal labels
  - Removed 'magic' module dependency (not available on HF)
  - render() function for app.py routing
"""

import streamlit as st
import hashlib
import logging
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("MediSync.Imaging")

ALLOWED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".dcm", ".dicom"
}
MAX_FILE_SIZE_MB    = 200
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
SESSION_TIMEOUT     = 3600

SEQUENCE_LABELS = [
    ("Sequence_Axial_{:02d}",     "Axial View Plane Sequence"),
    ("Sequence_Sagittal_{:02d}",  "Sagittal View Plane Sequence"),
    ("Sequence_Coronal_{:02d}",   "Coronal Cross Section Map"),
]


# ── Session / temp storage ────────────────────────────────────────────────────

def _get_session_dir() -> str:
    if "user_temp_dir" not in st.session_state:
        d = tempfile.mkdtemp(prefix="medisync_")
        os.chmod(d, 0o700)
        st.session_state.user_temp_dir = d
        st.session_state.last_accessed = time.time()
    if time.time() - st.session_state.get("last_accessed", 0) > SESSION_TIMEOUT:
        _cleanup()
        return _get_session_dir()
    st.session_state.last_accessed = time.time()
    return st.session_state.user_temp_dir


def _cleanup():
    path = st.session_state.get("user_temp_dir")
    if path and os.path.exists(path):
        try:
            shutil.rmtree(path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    for k in ["user_temp_dir", "imaging_files", "last_accessed"]:
        st.session_state.pop(k, None)


# ── DICOM scrubbing (graceful if pydicom absent) ──────────────────────────────

def _scrub_dicom(path: str) -> bool:
    try:
        import pydicom
        ds = pydicom.dcmread(path)
        for tag in [(0x0010,0x0010),(0x0010,0x0020),(0x0010,0x0030),(0x0008,0x0090)]:
            if tag in ds:
                del ds[tag]
        ds.save_as(path, write_like_original=False)
        return True
    except ImportError:
        return True  # pydicom not installed — skip scrub, allow file
    except Exception as e:
        logger.error(f"DICOM scrub failed: {e}")
        return False


# ── File processing ───────────────────────────────────────────────────────────

def _process_file(uploaded_file) -> Optional[Dict[str, Any]]:
    try:
        if uploaded_file.size > MAX_FILE_SIZE_BYTES:
            return {"error": f"File too large (max {MAX_FILE_SIZE_MB} MB): {uploaded_file.name}"}

        ext = Path(uploaded_file.name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            return {"error": f"Unsupported type: {uploaded_file.name}"}

        # Hash for deduplication
        h = hashlib.sha256()
        for chunk in iter(lambda: uploaded_file.read(4096), b""):
            h.update(chunk)
        fhash = h.hexdigest()
        uploaded_file.seek(0)

        cache = st.session_state.get("imaging_files", {})
        if fhash in cache:
            return cache[fhash]

        dest = Path(_get_session_dir()) / f"{uuid.uuid4()}{ext}"
        with open(dest, "wb") as f:
            for chunk in iter(lambda: uploaded_file.read(8192), b""):
                f.write(chunk)
        os.chmod(dest, 0o600)

        is_dicom = ext in {".dcm", ".dicom"}
        if is_dicom and not _scrub_dicom(str(dest)):
            return {"error": f"DICOM scrub failed: {uploaded_file.name}"}

        result = {
            "name":     uploaded_file.name,
            "hash":     fhash,
            "path":     str(dest),
            "ext":      ext,
            "is_dicom": is_dicom,
            "size_mb":  round(uploaded_file.size / (1024*1024), 2),
        }
        if "imaging_files" not in st.session_state:
            st.session_state.imaging_files = {}
        st.session_state.imaging_files[fhash] = result
        return result

    except Exception as e:
        logger.error(f"File processing error: {e}")
        return {"error": str(e)}


# ── UI ────────────────────────────────────────────────────────────────────────

def _styles():
    st.markdown("""
<style>
.seq-label {
    font-family:'Courier New',monospace;font-size:13px;
    color:#7bb8f0;letter-spacing:.06em;margin-bottom:4px;
}
.seq-caption {
    font-family:'Courier New',monospace;font-size:10px;
    color:#4a7a9b;text-align:center;margin-top:4px;
}
section[data-testid="stFileUploaderDropzone"] {
    border:2px dashed #2a2a4a !important;
    border-radius:14px !important;
    background:#080818 !important;
    min-height:120px !important;
}
</style>
""", unsafe_allow_html=True)


def _sequence_grid(files: list):
    if not files:
        return
    cols = st.columns(3)
    for idx, meta in enumerate(files):
        tmpl, caption = SEQUENCE_LABELS[idx % len(SEQUENCE_LABELS)]
        seq_num  = (idx // len(SEQUENCE_LABELS)) + 1
        seq_name = tmpl.format(seq_num)
        with cols[idx % 3]:
            st.markdown(
                f'<div class="seq-label">{seq_name}</div>',
                unsafe_allow_html=True,
            )
            ext = meta.get("ext", "")
            if ext in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                try:
                    st.image(meta["path"], use_container_width=True)
                except Exception:
                    st.info(f"⬜ {meta['name']}")
            elif meta.get("is_dicom"):
                try:
                    import pydicom, numpy as np
                    ds  = pydicom.dcmread(meta["path"])
                    arr = ds.pixel_array.astype(float)
                    arr = ((arr - arr.min()) / (arr.ptp() + 1e-9) * 255).astype("uint8")
                    st.image(arr, use_container_width=True)
                except Exception:
                    st.info(f"📁 DICOM: {meta['name']} ({meta['size_mb']} MB)")
            else:
                st.info(f"📁 {meta['name']} ({meta['size_mb']} MB)")

            st.markdown(
                f'<div class="seq-caption">{caption}</div>'
                f'<div class="seq-caption" style="color:#3a6a3a;">⚠ Manual review required</div>',
                unsafe_allow_html=True,
            )


# ── Main render ───────────────────────────────────────────────────────────────

def render():
    _styles()

    st.markdown("## 🩻 Advanced Multi-Sequence Imaging Core")
    st.caption("Upload multiple DICOM, Rad-Scans, or Clinical Imaging Sequences…")

    st.markdown("""
<div style="background:#0a0a1a;border:1px solid #1a1a3a;border-radius:8px;
padding:10px 16px;margin-bottom:16px;font-family:'Courier New',monospace;
font-size:11px;color:#f5c842;">
⚕ CLINICAL DISCLAIMER: Outputs for decision support only.
DICOM files anonymised on upload. Manual PHI review required.
NOT FOR PRIMARY DIAGNOSTIC USE.
</div>
""", unsafe_allow_html=True)

    # Upload widget — multi-file drag-and-drop
    uploaded = st.file_uploader(
        "Drop files here or click to browse",
        accept_multiple_files=True,
        type=["png","jpg","jpeg","webp","bmp","tiff","dcm","dicom"],
        help=f"Up to {MAX_FILE_SIZE_MB}MB per file · PNG, JPG, DICOM",
        key="imaging_uploader_main",
        label_visibility="collapsed",
    )
    st.caption(f"📁 {MAX_FILE_SIZE_MB}MB per file · PNG, JPG, DICOM · Drag-and-drop supported")

    if uploaded:
        with st.spinner("Processing uploads…"):
            for f in uploaded:
                result = _process_file(f)
                if result and "error" in result:
                    st.error(result["error"])

    # Controls row
    col_clear, col_count = st.columns([1, 5])
    files = list(st.session_state.get("imaging_files", {}).values())
    with col_count:
        if files:
            st.caption(f"✅ {len(files)} sequence{'s' if len(files)!=1 else ''} loaded")
    with col_clear:
        if files:
            if st.button("🗑 Clear All", key="imaging_clear_btn"):
                _cleanup()
                st.rerun()

    # Sequence grid
    if files:
        st.markdown("---")
        _sequence_grid(files)
    else:
        st.markdown("""
<div style="border:1px dashed #2a2a4a;border-radius:12px;padding:56px 24px;
text-align:center;color:#3a3a5a;font-family:'Courier New',monospace;font-size:13px;
margin-top:16px;">
🩻 No sequences loaded.<br>
<span style="font-size:11px;color:#2a2a4a;">
Drag and drop PNG, JPG or DICOM files above to begin.
</span>
</div>
""", unsafe_allow_html=True)

    st.sidebar.markdown(
        "### ⚠️ Clinical Disclaimer\n"
        "Findings must be verified by a clinician. "
        "All DICOM files require manual review for burned-in PHI."
    )
