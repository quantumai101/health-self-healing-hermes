"""
pages/ehr_summarizer.py — EHR Summarizer
Updated: 2026-05-14

Privacy model:
  - Local folder paths are stored PER USER in data/users/<id>/ehr_settings.json
  - Other users logging in NEVER see your folder paths or files
  - Each user configures their own paths via a UI panel in the sidebar
  - Uploaded files stored in data/users/<id>/ehr_uploads/  (private per user)
  - NOVA summaries stored in data/users/<id>/ehr_summaries/ (private per user)

.env is no longer used for paths — everything is per-user via the settings UI.
"""

import os
import io
import json
import time
import streamlit as st
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# PER-USER FOLDER HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _user_data_root() -> Path:
    """Root folder for the current logged-in user's data."""
    try:
        from auth.session import current_user_data_path
        return current_user_data_path("")
    except Exception:
        return Path("data/ehr_uploads_dev")


def _ehr_upload_dir() -> Path:
    d = _user_data_root() / "ehr_uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _summaries_dir() -> Path:
    d = _user_data_root() / "ehr_summaries"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _settings_path() -> Path:
    return _user_data_root() / "ehr_settings.json"


# ─────────────────────────────────────────────────────────────────────────────
# PER-USER PATH SETTINGS  (stored in data/users/<id>/ehr_settings.json)
# NOT in .env — so other users never see your paths
# ─────────────────────────────────────────────────────────────────────────────

def _load_user_settings() -> dict:
    """Load this user's local folder paths from their private settings file."""
    p = _settings_path()
    if not p.exists():
        return {"local_paths": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"local_paths": []}


def _save_user_settings(settings: dict) -> None:
    """Save this user's local folder paths to their private settings file."""
    _settings_path().write_text(
        json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _get_user_local_paths() -> list[str]:
    """Return the list of local folder paths configured by this user."""
    return _load_user_settings().get("local_paths", [])


def _add_user_local_path(new_path: str) -> None:
    settings = _load_user_settings()
    paths = settings.get("local_paths", [])
    if new_path not in paths:
        paths.append(new_path)
    settings["local_paths"] = paths
    _save_user_settings(settings)


def _remove_user_local_path(path_to_remove: str) -> None:
    settings = _load_user_settings()
    settings["local_paths"] = [
        p for p in settings.get("local_paths", []) if p != path_to_remove
    ]
    _save_user_settings(settings)


# ─────────────────────────────────────────────────────────────────────────────
# LOCAL PATH SCANNING  (uses per-user settings, not .env)
# ─────────────────────────────────────────────────────────────────────────────

SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".pdf", ".txt", ".webp", ".dcm"}


def _local_report_paths() -> list[Path]:
    """
    Scans folders saved in this user's private ehr_settings.json.
    Returns every supported file found (flat scan).
    Other users' settings are completely separate.
    """
    found: list[Path] = []
    for raw in _get_user_local_paths():
        folder = Path(raw.strip())
        if not folder.exists():
            continue
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXT:
                found.append(f)
    return found


# ─────────────────────────────────────────────────────────────────────────────
# PATH SETTINGS UI  (shown in sidebar, private to each user)
# ─────────────────────────────────────────────────────────────────────────────

def _render_path_settings_sidebar():
    """
    Sidebar panel where each user manages their own local folder paths.
    Completely private — other users see their own paths only.
    """
    with st.sidebar:
        st.divider()
        st.markdown("**📂 My Local Report Folders**")
        st.caption("Only you can see these — private to your account.")

        saved_paths = _get_user_local_paths()

        # Show existing paths with remove button
        for path_str in saved_paths:
            folder = Path(path_str)
            exists = folder.exists()
            if exists:
                count = sum(
                    1 for f in folder.iterdir()
                    if f.is_file() and f.suffix.lower() in SUPPORTED_EXT
                )
                st.success(f"✅ {folder.name} ({count} files)")
            else:
                st.warning(f"⚠️ Not found: `{path_str}`")
            if st.button("Remove", key=f"removepath_{path_str}",
                         use_container_width=True):
                _remove_user_local_path(path_str)
                st.rerun()

        # Add new path
        st.markdown("**Add a folder path:**")
        new_path = st.text_input(
            "Folder path",
            placeholder=r"C:\Medical Reports 17Feb2026",
            label_visibility="collapsed",
            key="new_local_path_input",
        )
        if st.button("➕ Add Path", use_container_width=True, key="add_path_btn"):
            if new_path.strip():
                cleaned = new_path.strip().strip('"').strip("'")
                if Path(cleaned).exists():
                    _add_user_local_path(cleaned)
                    st.success(f"✅ Added: `{cleaned}`")
                    st.rerun()
                else:
                    st.error(f"Folder not found: `{cleaned}`\nCheck the path and try again.")
            else:
                st.warning("Please enter a folder path.")


# ─────────────────────────────────────────────────────────────────────────────
# UPLOADED FILE STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def _save_uploaded_files(uploaded_files: list) -> list[Path]:
    upload_dir = _ehr_upload_dir()
    saved = []
    for uf in uploaded_files:
        dest = upload_dir / uf.name
        if not dest.exists():
            dest.write_bytes(uf.read())
        saved.append(dest)
    return saved


def _load_uploaded_files() -> list[Path]:
    return sorted(
        [f for f in _ehr_upload_dir().iterdir()
         if f.suffix.lower() in SUPPORTED_EXT],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )


def _delete_file(filepath: Path):
    try:
        filepath.unlink()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# MERGE ALL SOURCES
# ─────────────────────────────────────────────────────────────────────────────

def _all_available_files() -> tuple[list[Path], list[Path], list[Path]]:
    """Returns (local_files, uploaded_files, combined_deduplicated)."""
    local_files    = _local_report_paths()
    uploaded_files = _load_uploaded_files()
    seen: set[str] = set()
    combined: list[Path] = []
    for f in uploaded_files + local_files:
        if f.name not in seen:
            seen.add(f.name)
            combined.append(f)
    return local_files, uploaded_files, combined


# ─────────────────────────────────────────────────────────────────────────────
# FILE GROUPING
# ─────────────────────────────────────────────────────────────────────────────

def _group_files(files: list[Path]) -> dict[str, list[Path]]:
    groups: dict[str, list[Path]] = {
        "🩸 Blood / Labs":  [],
        "🧠 MRI / Imaging": [],
        "🫀 Cardiac":       [],
        "🔬 Other":         [],
    }
    for f in files:
        n = f.name.lower()
        if any(k in n for k in ["blood", "psa", "cholesterol", "creatine",
                                  "glucose", "lab", "eatine", "sterol"]):
            groups["🩸 Blood / Labs"].append(f)
        elif any(k in n for k in ["mri", "brain", "ct", "ctca", "dicom", "scan"]):
            groups["🧠 MRI / Imaging"].append(f)
        elif any(k in n for k in ["ecg", "cardiac", "heart", "dvt", "carotid",
                                    "stress", "kub", "ultrasound", "doppler"]):
            groups["🫀 Cardiac"].append(f)
        else:
            groups["🔬 Other"].append(f)
    return groups


def _sidebar_file_index(files: list[Path]):
    groups = _group_files(files)
    with st.sidebar:
        st.markdown("**📊 EHR File Index**")
        for label, grp in groups.items():
            if grp:
                st.caption(f"{label}: {len(grp)}")


# ─────────────────────────────────────────────────────────────────────────────
# PERSISTENT SUMMARY STORAGE
# ─────────────────────────────────────────────────────────────────────────────

def _summary_path(source_label: str) -> Path:
    safe = "".join(
        c if c.isalnum() or c in "-_" else "_" for c in source_label
    )[:60]
    return _summaries_dir() / f"{safe}.json"


def _save_summary(source_label: str, summary: str) -> None:
    payload = {
        "source":   source_label,
        "summary":  summary,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _summary_path(source_label).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_summary(source_label: str) -> dict | None:
    p = _summary_path(source_label)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_all_summaries() -> list[dict]:
    result = []
    for p in sorted(_summaries_dir().glob("*.json"),
                    key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            result.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            pass
    return result


def _delete_summary(source_label: str):
    try:
        _summary_path(source_label).unlink()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# TEXT EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text(filepath: Path) -> str:
    ext = filepath.suffix.lower()
    try:
        if ext == ".pdf":
            import PyPDF2
            with open(filepath, "rb") as f:
                return "".join(
                    p.extract_text() or "" for p in PyPDF2.PdfReader(f).pages
                ).strip()
        elif ext == ".txt":
            return filepath.read_text(encoding="utf-8", errors="ignore").strip()
        elif ext in {".jpg", ".jpeg", ".png", ".webp"}:
            return (
                f"[Medical image: {filepath.name}]\n"
                f"Path: {filepath}\n"
                f"Size: {round(filepath.stat().st_size / 1e6, 1)} MB\n"
                f"Please analyse this medical image."
            )
        elif ext == ".dcm":
            return (
                f"[DICOM file: {filepath.name}]\n"
                f"Path: {filepath}\n"
                f"Please analyse this DICOM medical scan."
            )
    except Exception as e:
        return f"[Could not extract text: {e}]"
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# UPLOAD UI SECTION
# ─────────────────────────────────────────────────────────────────────────────

def _render_upload_section() -> list[Path]:
    local_files, uploaded_files, all_files = _all_available_files()

    sources = []
    if local_files:
        sources.append(f"**{len(local_files)} from your local folders**")
    if uploaded_files:
        sources.append(f"**{len(uploaded_files)} uploaded**")
    status = "  •  ".join(sources) if sources else "No files found yet"

    st.markdown("#### 📁 Medical Records Library")
    st.caption(
        f"Formats: PDF, JPG, PNG, TXT, DICOM  •  {status}  •  "
        f"🔒 Private to your account only"
    )

    # Show local folder status
    saved_paths = _get_user_local_paths()
    if saved_paths:
        for path_str in saved_paths:
            folder = Path(path_str)
            if folder.exists():
                count = sum(
                    1 for f in folder.iterdir()
                    if f.is_file() and f.suffix.lower() in SUPPORTED_EXT
                )
                st.success(f"✅ Auto-loading from: `{path_str}` ({count} files)")
            else:
                st.warning(f"⚠️ Folder not found: `{path_str}` — update in sidebar")
    else:
        st.info(
            "💡 **Tip:** Add your local medical report folders in the sidebar "
            "(**My Local Report Folders**) to auto-load files without uploading."
        )

    # New file uploader
    st.markdown("**Upload files** (saved permanently to your private library):")
    newly_uploaded = st.file_uploader(
        label="Drop files here",
        type=["pdf", "jpg", "jpeg", "png", "txt", "webp"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key=st.session_state.get("ehr_uploader_key", "ehr_file_uploader_0"),
    )
    if newly_uploaded:
        new_paths = _save_uploaded_files(newly_uploaded)
        st.success(
            f"✅ Saved {len(new_paths)} file(s) to your private library: "
            f"{', '.join(p.name for p in new_paths[:3])}"
            + ("…" if len(new_paths) > 3 else "")
        )
        local_files, uploaded_files, all_files = _all_available_files()

    # Grouped display
    if all_files:
        groups = _group_files(all_files)
        for group_name, group_files in groups.items():
            if not group_files:
                continue
            with st.expander(
                f"{group_name} — {len(group_files)} file(s)", expanded=False
            ):
                for f in group_files:
                    is_local = f in local_files
                    col1, col2, col3, col4 = st.columns([5, 1, 1, 1])
                    col1.markdown(f"`{f.name}`")
                    col2.caption(f"{round(f.stat().st_size / 1e6, 1)} MB")
                    col3.caption("📂 local" if is_local else "⬆️ saved")
                    if not is_local:
                        if col4.button("🗑️", key=f"del_{f.name}",
                                       help="Remove from library"):
                            _delete_file(f)
                            st.rerun()

        if "ehr_auto_loaded" not in st.session_state:
            st.session_state["ehr_auto_loaded"] = True
            st.info(f"🔄 Auto-loaded {len(all_files)} file(s) from your private library.")
    else:
        st.info(
            "No files yet. Use the sidebar **My Local Report Folders** to point "
            "Hermes at your existing folders, or upload files above."
        )

    return all_files


# ─────────────────────────────────────────────────────────────────────────────
# MAIN RENDER
# ─────────────────────────────────────────────────────────────────────────────

def render() -> None:
    try:
        _render_inner()
    except Exception as e:
        import traceback
        st.error(f"❌ ehr_summarizer.py render() crashed: {e}")
        st.code(traceback.format_exc(), language="python")


def _render_inner() -> None:
    from agents.nova import NovaAgent
    from core.session import add_log
    from core.chat_widget import render_chat_widget

    _nova = NovaAgent()

    EXAMPLE_SUMMARY = """🌟 **[NOVA — EHR Summary]**

**Chief Complaint:** Chest pain and shortness of breath on exertion × 3 weeks

**Diagnosis:**
- Primary: Hypertensive heart disease (I11.0)
- Secondary: Type 2 diabetes mellitus, uncontrolled (E11.65)

**Current Medications:**
- Perindopril 10mg daily | Metformin 1000mg BD | Atorvastatin 40mg nocte | Aspirin 100mg daily

**Risk Flags:**
🔴 Stage 2 Hypertension — immediate medication review
🔴 Poorly controlled T2DM (HbA1c 8.1%) — endocrinology referral
🟡 Borderline renal function (eGFR 54) — monitor ACE inhibitor
"""

    DISCLAIMER = """<div style="background:#180800;border:1px solid #f57c5c33;border-radius:6px;
padding:7px 14px;color:#f57c5c;font-size:11px;margin-bottom:14px;">
⚕️ <strong>CLINICAL DISCLAIMER:</strong> AI summary for informational purposes only.
Must be reviewed by a qualified clinician before any clinical decision.
</div>"""

    if "ehr_uploader_key" not in st.session_state:
        st.session_state["ehr_uploader_key"] = "ehr_file_uploader_0"

    # ── Sidebar: per-user path settings + file index ──────────────────────────
    _render_path_settings_sidebar()

    st.markdown("# 🏥 EHR Summarizer")
    st.caption(
        "🔒 Your medical records are private to your account. "
        "Add local folders in the sidebar to auto-load files."
    )
    st.markdown(DISCLAIMER, unsafe_allow_html=True)

    tab_upload, tab_paste, tab_example = st.tabs([
        "📁 Upload Document", "✏️ Paste Clinical Notes", "📋 See Example Output"
    ])

    raw_text     = ""
    source_label = ""

    # ── TAB 1 ─────────────────────────────────────────────────────────────────
    with tab_upload:
        available_files = _render_upload_section()
        _sidebar_file_index(available_files)

        if available_files:
            st.divider()
            st.markdown("#### 🔍 Select a file to summarise with NOVA")
            chosen_name = st.selectbox(
                "Choose from your library:",
                options=["— select a file —"] + [f.name for f in available_files],
                key="ehr_file_selector",
            )
            if chosen_name != "— select a file —":
                selected = next(
                    (f for f in available_files if f.name == chosen_name), None
                )
                if selected:
                    raw_text     = _extract_text(selected)
                    source_label = f"Library:{chosen_name}"
                    if raw_text and not raw_text.startswith("["):
                        with st.expander("📃 View Extracted Text", expanded=False):
                            st.text_area("", raw_text[:3000], height=200, disabled=True)

    # ── TAB 2 ─────────────────────────────────────────────────────────────────
    with tab_paste:
        st.markdown("#### Paste Clinical Notes")
        pasted = st.text_area(
            "Paste any clinical text:", height=280,
            placeholder="Patient: 58yo male\nBP: 162/96 mmHg\nFasting glucose: 8.4 mmol/L…"
        )
        if pasted.strip():
            raw_text     = pasted.strip()
            source_label = "Pasted_clinical_notes"

    # ── TAB 3 ─────────────────────────────────────────────────────────────────
    with tab_example:
        st.markdown("#### Example AI Summary Output")
        st.markdown(
            f'<div class="agent-msg">{EXAMPLE_SUMMARY}</div>',
            unsafe_allow_html=True,
        )

    st.divider()

    # ── NOVA SUMMARISATION ────────────────────────────────────────────────────
    if raw_text:
        st.success(f"✅ **{len(raw_text):,} characters** ready — {source_label}")
        col1, col2 = st.columns([3, 1])
        with col1:
            detail_level = st.select_slider(
                "Summary Detail Level",
                options=["Brief", "Standard", "Detailed"],
                value="Standard",
            )
        with col2:
            focus_area = st.selectbox(
                "Clinical Focus",
                ["General", "Cardiology", "Endocrinology", "Respiratory", "Neurology"],
            )

        existing = _load_summary(source_label)
        if existing:
            st.info(
                f"💾 Saved summary found (generated {existing.get('saved_at', '')}).  "
                f"Showing below — click **Re-generate** for a fresh analysis."
            )
            st.markdown("#### 📋 AI Clinical Summary")
            st.markdown(
                f'<div class="agent-msg">{existing["summary"]}</div>',
                unsafe_allow_html=True,
            )
            col_dl, col_regen, col_del = st.columns([3, 2, 1])
            col_dl.download_button(
                "⬇️ Download (.txt)", data=existing["summary"],
                file_name=f"ehr_{source_label[:20]}.txt", mime="text/plain",
            )
            regen = col_regen.button("🔄 Re-generate", use_container_width=True)
            if col_del.button("🗑️ Delete summary"):
                _delete_summary(source_label)
                st.rerun()
        else:
            regen = False

        if not existing or regen:
            if st.button(
                "🧠 Generate NOVA Clinical Summary",
                use_container_width=True, type="primary",
            ) or regen:
                with st.spinner("NOVA analysing…"):
                    add_log(f"EHR_SUMMARIZE:{detail_level}/{focus_area}")
                    enhanced = (
                        f"Detail: {detail_level}\nFocus: {focus_area}\n\n"
                        f"{raw_text[:4000]}"
                    )
                    summary = _nova.summarize_ehr_text(enhanced)
                _save_summary(source_label, summary)
                add_log("EHR_SUMMARY_COMPLETE")
                st.markdown("#### 📋 AI Clinical Summary")
                st.markdown(
                    f'<div class="agent-msg">{summary}</div>',
                    unsafe_allow_html=True,
                )
                st.success("💾 Summary saved permanently — shown automatically next time.")
                st.download_button(
                    "⬇️ Download (.txt)", data=summary,
                    file_name=f"ehr_{source_label[:20]}.txt", mime="text/plain",
                )
    else:
        st.info("👆 Select a file from your library or paste clinical notes above to begin.")

    # ── ALL SAVED SUMMARIES ───────────────────────────────────────────────────
    all_summaries = _load_all_summaries()
    if all_summaries:
        st.divider()
        st.markdown("### 💾 All Saved NOVA Summaries")
        st.caption(
            f"{len(all_summaries)} summaries — 🔒 private to your account — "
            f"auto-loaded every session"
        )
        for s in all_summaries:
            with st.expander(
                f"📋 {s.get('source', '')}  —  {s.get('saved_at', '')}",
                expanded=False,
            ):
                st.markdown(
                    f'<div class="agent-msg">{s["summary"]}</div>',
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns([4, 1])
                c1.download_button(
                    "⬇️ Download", data=s["summary"],
                    file_name=f"ehr_{s.get('source', '')[:20]}.txt",
                    mime="text/plain",
                    key=f"dl_{s.get('source', '')}",
                )
                if c2.button("🗑️ Delete", key=f"delsumm_{s.get('source', '')}"):
                    _delete_summary(s.get("source", ""))
                    st.rerun()

    st.divider()

    # ── SENTIMENT & ENTITY ANALYSIS ───────────────────────────────────────────
    st.markdown("### 🧠 Clinical Note Sentiment & Entity Analysis")
    sentiment_text = st.text_area(
        "Paste a clinical note for sentiment analysis:", height=120,
        placeholder="Patient appears distressed…", key="sentiment_input",
    )
    if (
        st.button("🔍 Analyse Sentiment & Entities", use_container_width=True)
        and sentiment_text
    ):
        from agents.prometheus import PrometheusAgent
        with st.spinner("Analysing…"):
            result = PrometheusAgent().analyze_sentiment(sentiment_text)
        st.markdown(f'<div class="agent-msg">{result}</div>', unsafe_allow_html=True)

    render_chat_widget(page_key="ehr_summarizer")


# ⚠️ DO NOT call render() here — app.py calls it via page routing.
