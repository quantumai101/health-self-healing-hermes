"""
pages/imaging.py — MediSync Imaging page

Drop zone v4:
- Large inline SVG medical X-ray lightbox icon injected via JS into the
  native Streamlit dropzone (replaces tiny CSS ::before emoji).
- Per-file ✕ delete chips rendered below the drop box via JS — mirrors
  Streamlit's hidden file list and wires ✕ clicks to Streamlit's own
  delete buttons.
- Browse files button hidden — drag-drop and Ctrl+V only.
- No floating overlay div; drag events fire over the full dashed box.
"""

import streamlit as st
import io
import os
import hashlib

# ---------------------------------------------------------------------------
# SAFE IMPORTS
# ---------------------------------------------------------------------------
try:
    from core.gemini import gemini_chat as _gemini_chat
    _HAS_GEMINI_CHAT = True
except Exception:
    _HAS_GEMINI_CHAT = False

try:
    from core.session import add_log as _add_log
    _HAS_ADD_LOG = True
except Exception:
    _HAS_ADD_LOG = False


def _add_log_safe(msg: str):
    if _HAS_ADD_LOG:
        try:
            _add_log(msg)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
MODALITY_OPTIONS = [
    "Blood Test Report",
    "ECG / Cardiac Tracing",
    "Stress Test / Heart Ultrasound Report",
    "CTCA (CT Coronary Angiography)",
    "Chest X-Ray",
    "Abdominal X-Ray",
    "CT Chest",
    "CT Abdomen/Pelvis",
    "CT Head",
    "MRI Brain",
    "MRI Spine",
    "Ultrasound Abdomen",
    "Ultrasound Pelvis",
    "Ultrasound Cardiac (Echo)",
    "Ultrasound Thyroid",
    "Ultrasound Renal",
    "Mammogram",
    "Bone Scan",
    "Other",
]

IMAGING_SYSTEM_PROMPT = """You are a specialist medical imaging AI assistant working
within an Australian health system. When presented with a medical image (X-ray, CT,
CTCA, MRI, ultrasound, stress test, heart ultrasound, ECG, blood test report, or other
scan), provide a structured report matching the exact modality selected:

1. **Modality & Region** — identify the imaging/test type and anatomical region
2. **Image Quality** — comment on quality, positioning, exposure (if applicable)
3. **Findings** — systematic description of all visible structures or values
4. **Abnormalities** — clearly flag any abnormal findings with severity
5. **Impression** — concise summary of key findings
6. **Recommendations** — suggested follow-up, additional views, or referrals
7. **Risk Level** — CRITICAL / HIGH / MODERATE / LOW / NORMAL

For Stress Test / Heart Ultrasound: analyse wall motion, ejection fraction,
stress-induced changes, and any ischaemic findings.
For CTCA: focus on coronary artery calcification, stenosis, CAD-RADS score,
plaque characteristics, and incidental findings.
For Blood Test Reports: interpret all values against reference ranges, flag abnormals.

IMPORTANT DISCLAIMER: This is an AI assistant for educational and workflow support
purposes only. All findings must be reviewed and verified by a qualified clinician
before any clinical decision is made. Not for diagnostic use."""

OFFLINE_REPORT = """## 🩻 Imaging Report — MediSync AI (Offline Simulation)

**Modality:** Chest X-Ray (PA view)
**Date:** 2026-05-05
**Patient ID:** P-004821

---

### Image Quality
Adequate inspiratory effort. Well-centred projection. No rotation artefact.

### Findings

**Cardiac:**
- Cardiothoracic ratio 0.48 — within normal limits

**Lungs & Pleura:**
- Mild increased interstitial markings in the left lower zone
- No pleural effusion. No pneumothorax.

**Mediastinum:** Trachea midline. No mediastinal widening.

**Bones & Soft Tissue:** No acute bony injury.

---

### Impression
> 🟠 **Mild left lower zone interstitial changes** — differential includes early
> consolidation vs atelectasis.

### Recommendations
1. Clinical correlation with symptoms
2. Repeat CXR in 4–6 weeks if symptoms persist

**Risk Level:** 🟠 MODERATE

---
⚠️ *AI simulation — offline mode. Connect live API for real image analysis.*"""

IMAGING_SUGGESTED_OPS = [
    ("🩻 Analyse all queued scans for critical findings",
     "Analyse all queued scans for critical findings and flag any urgent results"),
    ("❤️ Check ECG for heart failure or stroke risk",
     "Analyse the ECG tracing carefully for any potential earlier heart failure risk or stroke sign"),
    ("🫁 Compare chest X-rays for progression",
     "Compare the chest X-rays in the queue and describe any interval change or progression"),
    ("📋 Generate a structured radiology summary report",
     "Generate a structured executive radiology summary report for all scans in the queue"),
    ("🔬 Cross-reference findings with uploaded reports",
     "Cross-reference the imaging findings with any attached clinical or lab reports"),
    ("⚠️ Flag any CRITICAL or HIGH risk findings immediately",
     "Scan all images and immediately flag any CRITICAL or HIGH risk findings with recommendations"),
]

# ---------------------------------------------------------------------------
# CSS + JS
#
# Key design decision:
#   The dashed drop zone IS the native Streamlit file_uploader dropzone element
#   (section[data-testid="stFileUploaderDropzone"]).
#   We style it with the dark dashed border, correct height, and flex layout.
#   The icon + label text is injected via a CSS ::before pseudo-element so
#   it lives inside the same DOM node — drag events fire over the whole box.
#   No separate floating <div> overlay is used (that was the v2 misalignment bug).
# ---------------------------------------------------------------------------
PAGE_CSS = r"""
<style>
/* ── Scan cards ─────────────────────────────────────────────────────────── */
.scan-card {
    border: 1px solid #1c1c2e;
    border-radius: 10px;
    background: #0c0c18;
    padding: 16px;
    margin-bottom: 14px;
}
.scan-card-hdr {
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    color: #444460;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 10px;
}

/* ── Auto-expand textareas ─────────────────────────────────────────────── */
.stTextArea textarea {
    overflow-y: hidden !important;
    resize: none !important;
    min-height: 56px;
    transition: height 0.1s ease;
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   DARK DASHED DROP ZONE — styled directly on the native Streamlit widget
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

/* Hide default label (we use label_visibility="collapsed" in Python too) */
div[data-testid="stFileUploader"] > label {
    display: none !important;
}

/* The dropzone container ─────────────────────────────────────────────── */
section[data-testid="stFileUploaderDropzone"] {
    border: 2px dashed #2a2a4a !important;
    border-radius: 14px !important;
    background: #08080f !important;
    min-height: 210px !important;
    padding: 0 24px !important;
    margin-bottom: 4px !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    /* center content vertically — no Browse button at bottom any more */
    justify-content: center !important;
    cursor: pointer !important;
    position: relative !important;
    transition: background 0.2s, border-color 0.2s, box-shadow 0.2s !important;
    box-sizing: border-box !important;
}

/* Drag-over / hover glow */
section[data-testid="stFileUploaderDropzone"]:hover,
section[data-testid="stFileUploaderDropzone"]:focus-within {
    background: #0d0d1b !important;
    border-color: #f5c842 !important;
    box-shadow: 0 0 0 4px #f5c84220 !important;
}

/* Hide Streamlit's own drag-drop instructions block */
div[data-testid="stFileUploaderDropzoneInstructions"] {
    display: none !important;
}

/* Hide ALL buttons inside the dropzone (Browse/Upload) — drag-drop and Ctrl+V only */
section[data-testid="stFileUploaderDropzone"] button,
section[data-testid="stFileUploaderDropzone"] button[data-testid="baseButton-secondary"],
section[data-testid="stFileUploaderDropzone"] button[data-testid="baseButton-primary"],
div[data-testid="stFileUploaderDropzone"] button {
    display: none !important;
}

/* Hide Streamlit's native file rows — we render our own chips */
div[data-testid="stFileUploaderFileData"] {
    visibility: hidden !important;
    height: 0 !important;
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
}

/* ── Drop zone: use ::before for the large icon (SVG data URI) ──────── */
/* This is CSS-only so it always renders regardless of JS timing.        */
section[data-testid="stFileUploaderDropzone"]::before {
    content: "";
    display: block;
    width: 88px;
    height: 88px;
    margin: 0 auto 4px auto;
    flex-shrink: 0;
    background-image: url("data:image/svg+xml,%3Csvg width='88' height='88' viewBox='0 0 88 88' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Crect x='7' y='6' width='74' height='58' rx='6' fill='%230a0a18' stroke='%233a3a5a' stroke-width='2.2'/%3E%3Crect x='12' y='11' width='64' height='48' rx='4' fill='%230d1525'/%3E%3Cellipse cx='44' cy='35' rx='20' ry='24' stroke='%234466aa' stroke-width='1.4' fill='none' opacity='.6'/%3E%3Cline x1='44' y1='13' x2='44' y2='57' stroke='%235577bb' stroke-width='1.6' opacity='.5'/%3E%3Cpath d='M44 20Q30 22 28 32' stroke='%234466aa' stroke-width='1.1' fill='none' opacity='.55'/%3E%3Cpath d='M44 27Q29 30 27 39' stroke='%234466aa' stroke-width='1.1' fill='none' opacity='.42'/%3E%3Cpath d='M44 34Q30 37 28 45' stroke='%234466aa' stroke-width='1.1' fill='none' opacity='.3'/%3E%3Cpath d='M44 20Q58 22 60 32' stroke='%234466aa' stroke-width='1.1' fill='none' opacity='.55'/%3E%3Cpath d='M44 27Q59 30 61 39' stroke='%234466aa' stroke-width='1.1' fill='none' opacity='.42'/%3E%3Cpath d='M44 34Q58 37 60 45' stroke='%234466aa' stroke-width='1.1' fill='none' opacity='.3'/%3E%3Cellipse cx='41' cy='37' rx='8' ry='9' fill='%231a2a3a' stroke='%233355aa' stroke-width='1.1' opacity='.7'/%3E%3Cellipse cx='32' cy='33' rx='7' ry='10' fill='%230d1e35' stroke='%232244aa' stroke-width='.9' opacity='.5'/%3E%3Cellipse cx='56' cy='33' rx='7' ry='10' fill='%230d1e35' stroke='%232244aa' stroke-width='.9' opacity='.5'/%3E%3Crect x='34' y='65' width='20' height='5' rx='2.5' fill='%231a1a2e'/%3E%3Crect x='27' y='70' width='34' height='4' rx='2' fill='%231a1a2e'/%3E%3Cpath d='M40 44L44 38L48 44' stroke='%23f5c842' stroke-width='2' stroke-linecap='round' stroke-linejoin='round' fill='none'/%3E%3Cline x1='44' y1='38' x2='44' y2='52' stroke='%23f5c842' stroke-width='2' stroke-linecap='round'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: center;
    background-size: contain;
    pointer-events: none;
}

/* ── Drop zone: ::after for the text labels ─────────────────────────── */
section[data-testid="stFileUploaderDropzone"]::after {
    content: "Drop scans here  ·  Ctrl+V to paste\A JPG  PNG  WEBP  BMP  TIFF  DICOM\A Multiple files supported";
    white-space: pre;
    display: block;
    text-align: center;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.07em;
    line-height: 2.3;
    color: #7777aa;
    pointer-events: none;
    flex-shrink: 0;
    margin-bottom: 8px;
}

section[data-testid="stFileUploaderDropzone"]:hover::before,
section[data-testid="stFileUploaderDropzone"]:hover::after {
    opacity: 0.85;
}

/* ── Per-file delete chips ───────────────────────────────────────────── */
#hdw-file-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 10px 4px 4px 4px;
}
.hdw-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    background: #0e0e1c;
    border: 1px solid #2a2a40;
    border-radius: 6px;
    padding: 5px 8px 5px 8px;
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    color: #7777aa;
    max-width: 260px;
    min-width: 0;
}
.hdw-chip-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    flex: 1;
    min-width: 0;
}
.hdw-chip-x {
    cursor: pointer;
    font-size: 13px;
    color: #555577;
    line-height: 1;
    flex-shrink: 0;
    padding: 0 2px;
    transition: color 0.15s;
    user-select: none;
}
.hdw-chip-x:hover { color: #f5c842; }
</style>

<script>
(function () {
    if (window.__hdwImgV4) return;
    window.__hdwImgV4 = true;

    /* ── Per-file delete chips ─────────────────────────────────────────
       Streamlit renders file rows in div[data-testid="stFileUploaderFileData"].
       We hide those via CSS and build our own chip bar with ✕ buttons.
       Each ✕ programmatically clicks Streamlit's own hidden delete button.
       Uses polling so it works even after React re-renders.              */

    let _lastFileCount = -1;

    function buildChips() {
        const uploaderRoot = document.querySelector('div[data-testid="stFileUploader"]');
        if (!uploaderRoot) return;

        const fileRows  = uploaderRoot.querySelectorAll('[data-testid="stFileUploaderFileName"]');
        const delBtns   = uploaderRoot.querySelectorAll('div[data-testid="stFileUploaderFileData"] button');
        const fileCount = fileRows.length;

        // Find or create chip bar — placed right after the uploader widget
        let chipBar = document.getElementById('hdw-file-chips');
        if (!chipBar) {
            chipBar = document.createElement('div');
            chipBar.id = 'hdw-file-chips';
            uploaderRoot.after(chipBar);
        }

        // Skip rebuild if nothing changed
        if (fileCount === _lastFileCount && chipBar.children.length === fileCount) return;
        _lastFileCount = fileCount;

        chipBar.innerHTML = '';
        fileRows.forEach((row, i) => {
            const name = row.textContent.trim();
            if (!name) return;

            const chip = document.createElement('div');
            chip.className = 'hdw-chip';

            // Tiny scan icon
            const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            icon.setAttribute('width', '13');
            icon.setAttribute('height', '13');
            icon.setAttribute('viewBox', '0 0 13 13');
            icon.setAttribute('fill', 'none');
            icon.style.cssText = 'flex-shrink:0;opacity:0.55';
            icon.innerHTML = `
                <rect x="1" y="1" width="11" height="11" rx="2" stroke="#5577aa" stroke-width="1.2"/>
                <line x1="4" y1="4" x2="4" y2="9" stroke="#5577aa" stroke-width="1"/>
                <line x1="6.5" y1="3" x2="6.5" y2="10" stroke="#5577aa" stroke-width="1"/>
                <line x1="9" y1="5" x2="9" y2="9" stroke="#5577aa" stroke-width="1"/>
            `;

            const label = document.createElement('span');
            label.className = 'hdw-chip-name';
            label.title = name;
            label.textContent = name;

            const x = document.createElement('span');
            x.className = 'hdw-chip-x';
            x.title = 'Remove file';
            x.textContent = '✕';
            x.dataset.idx = String(i);
            x.addEventListener('click', function(e) {
                e.stopPropagation();
                const idx = parseInt(this.dataset.idx, 10);
                const btn = uploaderRoot.querySelectorAll(
                    'div[data-testid="stFileUploaderFileData"] button'
                )[idx];
                if (btn) btn.click();
            });

            chip.appendChild(icon);
            chip.appendChild(label);
            chip.appendChild(x);
            chipBar.appendChild(chip);
        });
    }

    /* ── Auto-expand textareas ────────────────────────────────────────── */
    function autoExpand(ta) {
        ta.style.height = 'auto';
        ta.style.height = ta.scrollHeight + 'px';
    }
    function attachExpand(ta) {
        if (ta.__hdwExp) return;
        ta.__hdwExp = true;
        ta.style.overflowY = 'hidden';
        ta.style.resize    = 'none';
        autoExpand(ta);
        ta.addEventListener('input', () => autoExpand(ta));
    }

    /* ── Poll every 400ms — catches React re-renders reliably ─────────── */
    setInterval(function () {
        buildChips();
        document.querySelectorAll('textarea').forEach(attachExpand);
    }, 400);

    // Also run immediately and on mutations
    buildChips();
    new MutationObserver(buildChips).observe(document.body, {
        childList: true, subtree: true
    });

    /* ── Ctrl+V paste → inject into native file input ─────────────────── */
    window.addEventListener('paste', function (e) {
        const items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        const imageFiles = Array.from(items)
            .filter(i => i.kind === 'file' && i.type.startsWith('image/'))
            .map(i => i.getAsFile());
        if (!imageFiles.length) return;
        e.preventDefault();
        const nativeInput = document.querySelector(
            'section[data-testid="stFileUploaderDropzone"] input[type="file"]'
        );
        if (!nativeInput) return;
        const dt = new DataTransfer();
        imageFiles.forEach(f => dt.items.add(f));
        nativeInput.files = dt.files;
        nativeInput.dispatchEvent(new Event('change', { bubbles: true }));
    }, true);
})();
</script>
"""


# ---------------------------------------------------------------------------
# AI helpers
# ---------------------------------------------------------------------------
def _analyse_image(image_bytes, mime_type, modality, notes, global_context=""):
    _add_log_safe(f"IMAGING:analyse:{modality}")
    extra = f"\n\nClinical context:\n{global_context.strip()}" if global_context.strip() else ""
    prompt = (
        f"Analyse this medical image/report and provide a structured clinical report.\n\n"
        f"Modality/Type: {modality}\nClinical notes: {notes or 'None'}{extra}\n\n"
        f"Provide a complete structured report."
    )
    try:
        import google.generativeai as genai
        import PIL.Image as PILImage
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("No API key")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        pil_img = PILImage.open(io.BytesIO(image_bytes))
        return model.generate_content([IMAGING_SYSTEM_PROMPT + "\n\n" + prompt, pil_img]).text
    except Exception:
        if _HAS_GEMINI_CHAT:
            try:
                return _gemini_chat(
                    prompt=prompt,
                    system_prompt=IMAGING_SYSTEM_PROMPT,
                    offline_fallback=OFFLINE_REPORT,
                )
            except Exception:
                pass
    return OFFLINE_REPORT


def _chat_with_imaging_context(user_msg, global_context):
    _add_log_safe(f"IMAGING:chat:{user_msg[:60]}")
    system = IMAGING_SYSTEM_PROMPT + "\n\nAlso act as a clinical assistant for imaging questions."
    queue  = st.session_state.get("img_queue", [])
    context = ""
    if global_context.strip():
        context += f"\n\nClinical context:\n{global_context.strip()}"
    if queue:
        context += f"\n\nQueued scans: {', '.join(e['name'] for e in queue)}"
    if _HAS_GEMINI_CHAT:
        try:
            return _gemini_chat(
                prompt=user_msg + context,
                system_prompt=system,
                offline_fallback="*(Offline)* Connect API key for live responses.",
            )
        except Exception:
            pass
    return "*(Offline simulation)* Connect a live Gemini API key for real responses."


# ---------------------------------------------------------------------------
# Session / persistence
# ---------------------------------------------------------------------------
SCAN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "scans"
)
_MIME_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "bmp": "image/bmp", "tiff": "image/tiff",
    "tif": "image/tiff", "dcm": "application/dicom",
}


def _load_saved_scans() -> list:
    entries = []
    if not os.path.isdir(SCAN_DIR):
        return entries
    for fname in sorted(os.listdir(SCAN_DIR)):
        fpath = os.path.join(SCAN_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "rb") as f:
                img_bytes = f.read()
            ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else "jpg"
            mime = _MIME_MAP.get(ext, "image/jpeg")
            modality_raw = (
                fname.split("__")[0].replace("_", " ").replace("-", "/")
                if "__" in fname else "Blood Test Report"
            )
            entries.append({
                "bytes": img_bytes, "mime": mime, "name": fname,
                "modality": modality_raw, "notes": "", "report": None,
                "saved_path": fpath, "chat": [],
            })
        except Exception:
            continue
    return entries


def _init_state():
    for key, default in [
        ("img_global_notes", ""),
        ("img_chat_history", []),
        ("img_chat_sug_clicked", ""),
        ("img_scans_loaded", False),
        ("img_uploader_key", 0),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default
    if not st.session_state.img_scans_loaded:
        st.session_state.img_queue = _load_saved_scans()
        st.session_state.img_scans_loaded = True
    elif "img_queue" not in st.session_state:
        st.session_state.img_queue = []


def _queue_add(image_bytes, mime_type, name) -> bool:
    digest = hashlib.md5(image_bytes).hexdigest()
    existing = {hashlib.md5(e["bytes"]).hexdigest() for e in st.session_state.img_queue}
    if digest not in existing:
        st.session_state.img_queue.append({
            "bytes": image_bytes, "mime": mime_type, "name": name,
            "modality": "Blood Test Report", "notes": "", "report": None, "chat": [],
        })
        return True
    return False


# ---------------------------------------------------------------------------
# RENDER
# ---------------------------------------------------------------------------
def render() -> None:
    from auth.session import require_auth
    require_auth()
    _init_state()

    st.markdown(PAGE_CSS, unsafe_allow_html=True)

    # ── Title ──────────────────────────────────────────────────────────────
    st.markdown("# 🤖 Health Digital Workforce")
    st.caption("🩻 MediSync Imaging · AI-powered radiology & clinical report analysis")
    st.divider()

    # ── Drop zone — native file uploader styled as the dashed dark box ─────
    # CSS above turns `section[data-testid="stFileUploaderDropzone"]` into the
    # dashed box and injects the icon/text via ::before. No separate HTML div.
    uploaded_files = st.file_uploader(
        label="Upload scans",
        type=["jpg", "jpeg", "png", "webp", "bmp", "tiff", "tif", "dcm"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key=f"img_native_uploader_{st.session_state.img_uploader_key}",
    )

    if uploaded_files:
        added_any = False
        for uf in uploaded_files:
            img_bytes = uf.read()
            mime = uf.type or "image/png"
            if _queue_add(img_bytes, mime, uf.name):
                added_any = True
        st.session_state.img_uploader_key += 1   # reset widget so it clears
        if added_any:
            st.rerun()

    # ── Chat section ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("### 💬 Imaging Assistant")

    for msg in st.session_state.img_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    st.markdown(
        "<p style='font-family:\"Space Mono\",monospace;font-size:9px;"
        "color:#3a3a5a;letter-spacing:0.18em;text-transform:uppercase;"
        "margin:8px 0 8px 0;'>✦ SUGGESTED HEALTH OPERATIONS</p>",
        unsafe_allow_html=True,
    )

    for op_idx in range(0, len(IMAGING_SUGGESTED_OPS), 2):
        pair = IMAGING_SUGGESTED_OPS[op_idx: op_idx + 2]
        cols = st.columns(len(pair))
        for col_idx, (col, (btn_label, btn_prompt)) in enumerate(zip(cols, pair)):
            with col:
                if st.button(btn_label, key=f"img_sug_{op_idx + col_idx}",
                             use_container_width=True):
                    st.session_state.img_chat_sug_clicked = btn_prompt
                    st.rerun()

    st.write("")
    prefill = st.session_state.get("img_chat_sug_clicked", "") or ""
    if prefill:
        st.session_state["img_chat_sug_clicked"] = ""

    user_input = st.chat_input(
        placeholder="Ask about imaging findings, blood test results, clinical risk…",
        key="img_chat_input_widget",
    )
    pending = user_input or prefill or ""
    if pending:
        with st.chat_message("user"):
            st.markdown(pending)
        st.session_state.img_chat_history.append({"role": "user", "content": pending})
        with st.chat_message("assistant"):
            with st.spinner("🤖 Analysing…"):
                reply = _chat_with_imaging_context(
                    pending, st.session_state.img_global_notes
                )
            st.markdown(reply)
        st.session_state.img_chat_history.append({"role": "assistant", "content": reply})
        st.rerun()

    # ── Pinned Demo Examples ───────────────────────────────────────────────
    st.divider()
    st.markdown(
        "<p style='font-family:\"Space Mono\",monospace;font-size:9px;"
        "color:#3a3a5a;letter-spacing:0.18em;text-transform:uppercase;"
        "margin:4px 0 8px 0;'>📌 PINNED AI ASSISTANT DEMO EXAMPLES</p>",
        unsafe_allow_html=True,
    )

    with st.expander("💬 Example 1 — Vascular Diagnostic Analysis (Westmead Hospital)",
                     expanded=False):
        st.markdown("""
**🧑‍⚕️ Patient Question:**
> *"You are the expert of Westmead Hospital Vascular Consultant Clinic — facing the attached
> medical reports, how can you find the true reasons why the patient experienced consistent
> left chest tightness and occasional sharp pain for a few minutes over the past two years?"*

---

**🤖 AI Imaging Assistant Response:**

As a specialist AI assistant, I have reviewed all queued reports. To find the true reason, we
must integrate the **anatomical** findings (CTCA, Carotid Doppler) with **functional** findings
(Stress Test, ECG) and **metabolic** risk factors (Blood tests).

**1. The "Normal" Findings — Ruling Out the Obvious**
- **CTCA (20 April 2026):** Calcium Score 0, CAD-RADS 0 — no plaque or narrowing.
  Classic coronary artery disease is **ruled out**.
- **Carotid & Peripheral Dopplers:** No significant stenosis or DVT — systemic large-vessel
  atherosclerosis **ruled out**.
- **Echocardiogram:** Normal pumping function (EF 64.2%) — structural failure **ruled out**.

**2. The "Hidden" Clues**
- **Mild Diastolic Dysfunction:** Impaired relaxation noted on Echo — linked to
  **Microvascular Dysfunction**.
- **Mildly Dilated Ascending Aorta (3.8 cm):** Suggests long-term blood pressure stress.
- **High LDL (4.8 mmol/L):** Drives inflammation and vascular tone issues even with clear arteries.

**3. Potential True Reasons**

| Suspect | Mechanism | Evidence |
|---|---|---|
| **Coronary Microvascular Dysfunction (CMD)** | Microscopic vessels don't dilate — invisible on CTCA | Diastolic dysfunction + clear CTCA |
| **Vasospastic Angina (Prinzmetal)** | Artery spasms despite clear anatomy | Sharp brief episodes + normal anatomy |
| **Oesophageal Spasm / GERD** | Mimics cardiac tightness perfectly | Needs gastro correlation |
| **Musculoskeletal (Costochondritis)** | Sharp pain reproducible by touch or movement | Needs clinical examination |

**4. Recommended Next Steps**
1. **Cardiac Stress MRI or PET Scan** — evaluates microvascular blood flow under stress
2. **24-Hour Holter Monitor** — correlates pain episodes with rhythm disturbances
3. **Aggressive Lipid Management** — statin therapy targeting LDL below 1.8 mmol/L
4. **Nitrate Trial** — sublingual GTN relief confirms vascular (spasm/microvascular) origin

**Risk Level:** 🟠 **HIGH**

> ⚕️ *DISCLAIMER: AI report for clinical support only. All findings must be verified by the
> attending Vascular Consultant or Cardiologist before any treatment plan.*
        """)

    with st.expander(
        "💬 Example 2 — Questions to Ask at Your Westmead Vascular Clinic Appointment",
        expanded=False,
    ):
        st.markdown("""
**🧑‍⚕️ Patient Question:**
> *"Can you draft a list of questions I should ask during the appointment with Westmead Hospital
> Vascular Consultant Clinic experts?"*

---

**🤖 AI Imaging Assistant Response:**

**1. Regarding the Carotid Doppler**
- *"What is the exact percentage of stenosis in my carotid arteries?"*
- *"Is the plaque 'stable' or 'unstable/soft'?"*

**2. Regarding the DVT Ultrasound**
- *"Was a DVT clot found, and if so, is it occlusive?"*
- *"How long will I need blood thinners?"*

**3. Regarding CTCA & Heart Health**
- *"My CTCA shows CAD-RADS 0 — does clear coronary anatomy change the vascular management
  approach?"*

**4. Medication & Risk Factor Management**
- *"My LDL is 4.8 mmol/L — is this low enough for my vascular profile?"*

**Risk Level:** 🟠 **MODERATE to HIGH**

> ⚕️ *DISCLAIMER: For educational preparation only.*
        """)

    st.divider()

    # ── Image queue ────────────────────────────────────────────────────────
    queue = st.session_state.img_queue

    if not queue:
        st.markdown(
            "<div style='text-align:center;color:#2a2a40;padding:24px 0 12px;"
            "font-family:Space Mono,monospace;font-size:11px;letter-spacing:0.12em;'>"
            "NO SCANS QUEUED — DROP FILES INTO THE BOX ABOVE TO BEGIN</div>",
            unsafe_allow_html=True,
        )
        for col, (icon, label) in zip(st.columns(4), [
            ("🫁", "Chest X-Ray\nCT Chest"), ("🧠", "CT Head\nMRI Brain"),
            ("🫀", "Cardiac Echo\nECG Tracing"), ("🩸", "Blood Test\nReport"),
        ]):
            with col:
                st.markdown(
                    f"<div style='text-align:center;background:#0e0e1a;"
                    f"border:1px solid #1a1a2a;border-radius:8px;padding:16px 8px;'>"
                    f"<div style='font-size:28px;margin-bottom:6px;'>{icon}</div>"
                    f"<div style='font-size:10px;color:#666680;line-height:1.5;"
                    f"font-family:JetBrains Mono,monospace;white-space:pre-line;'>{label}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        return

    # ── Queue header ───────────────────────────────────────────────────────
    hdr_col, clr_col = st.columns([5, 1])
    with hdr_col:
        st.markdown(
            f"<p style='font-family:Space Mono,monospace;font-size:11px;"
            f"color:#444460;letter-spacing:0.1em;text-transform:uppercase;margin:0;'>"
            f"✦ SCAN QUEUE — {len(queue)} image{'s' if len(queue) != 1 else ''}</p>",
            unsafe_allow_html=True,
        )
    with clr_col:
        if st.button("🗑️ Clear all", key="img_clear_all", use_container_width=True):
            st.session_state.img_queue = []
            st.rerun()

    st.write("")

    # ── Per-image cards ────────────────────────────────────────────────────
    for idx, entry in enumerate(queue):
        if "chat" not in entry:
            entry["chat"] = []

        st.markdown("<div class='scan-card'>", unsafe_allow_html=True)

        col_name, col_mod, col_save, col_del = st.columns([3, 2.5, 1, 1])

        with col_name:
            st.markdown(
                f"<div class='scan-card-hdr' style='padding-top:8px;'>"
                f"SCAN {idx + 1} · {entry['name']}</div>",
                unsafe_allow_html=True,
            )

        with col_mod:
            chosen_modality = st.selectbox(
                "Modality", MODALITY_OPTIONS,
                index=MODALITY_OPTIONS.index(entry.get("modality", "Blood Test Report"))
                      if entry.get("modality") in MODALITY_OPTIONS else 0,
                key=f"img_modality_{idx}",
                label_visibility="collapsed",
            )
            entry["modality"] = chosen_modality

        with col_save:
            already_saved = entry.get("saved_path")
            if st.button(
                "✅ Saved" if already_saved else "💾 Save",
                key=f"img_save_{idx}",
                use_container_width=True,
            ):
                try:
                    save_dir = os.path.join(
                        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "scans",
                    )
                    os.makedirs(save_dir, exist_ok=True)
                    safe_mod  = chosen_modality.replace("/", "-").replace(" ", "_")
                    safe_name = entry["name"].replace(" ", "_")
                    save_path = os.path.join(save_dir, f"{safe_mod}__{safe_name}")
                    with open(save_path, "wb") as fout:
                        fout.write(entry["bytes"])
                    entry["saved_path"] = save_path
                    _add_log_safe(f"SCAN_SAVED:{safe_mod}__{safe_name}")
                    st.success("✅ Saved")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Save failed: {e}")

        with col_del:
            if st.button("🗑️ Delete", key=f"img_del_{idx}", use_container_width=True):
                st.session_state.img_queue.pop(idx)
                st.rerun()

        if entry["name"].lower().endswith(".dcm"):
            st.warning("⚠️ DICOM — cannot render preview. AI will analyse metadata only.")
        else:
            st.image(entry["bytes"], use_container_width=True)

        for msg in entry["chat"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        scan_input_col, scan_send_col = st.columns([11, 1])
        with scan_input_col:
            scan_msg = st.text_area(
                label=f"scan_chat_{idx}",
                label_visibility="collapsed",
                value="",
                placeholder="Ask about this scan — findings, risks, follow-up…",
                height=68,
                key=f"img_scan_input_{idx}",
            )
        with scan_send_col:
            st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
            scan_send = st.button("↑", key=f"img_scan_send_{idx}", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        if scan_send and scan_msg and scan_msg.strip():
            user_text = scan_msg.strip()
            entry["chat"].append({"role": "user", "content": user_text})
            with st.spinner("🤖 Analysing scan…"):
                reply = _analyse_image(
                    entry["bytes"], entry["mime"], chosen_modality,
                    notes=user_text,
                    global_context=st.session_state.img_global_notes,
                )
            entry["chat"].append({"role": "assistant", "content": reply})
            st.rerun()

        replies = [m["content"] for m in entry["chat"] if m["role"] == "assistant"]
        if replies:
            st.download_button(
                "⬇️ Download Latest Report (.md)", data=replies[-1],
                file_name=f"report_{entry['name']}.md", mime="text/markdown",
                key=f"img_dl_{idx}",
            )

        st.markdown("</div>", unsafe_allow_html=True)
        st.write("")


# ---------------------------------------------------------------------------
# Multipage entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    render()
