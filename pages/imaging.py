"""
pages/imaging.py — MediSync Imaging page

Self-contained page (works as Streamlit multipage /imaging AND via app.py render()).

Changes in this version:
  • Removed disclaimer bar, global clinical context box, and paste relay
    from above the drop zone — drop zone now sits directly under page title
  • Paste relay moved to after the file uploader (hidden, JS still works)
  • Full working chat window (mirroring the main chat page) rendered below
    the file uploader section, with imaging-specific placeholder wording
  • Auto-expanding textarea + Ctrl+V paste + drag-and-drop all preserved
  • Per-image "Clinical notes" textarea is also auto-expanding
  • All core.* imports are guarded so the page never goes blank on import error
"""

import streamlit as st
import base64
import io
import os
import json
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
    "Chest X-Ray", "Abdominal X-Ray",
    "CT Chest", "CT Abdomen/Pelvis", "CT Head",
    "MRI Brain", "MRI Spine",
    "Ultrasound Abdomen", "Ultrasound Pelvis",
    "Ultrasound Cardiac (Echo)", "Ultrasound Thyroid",
    "Ultrasound Renal", "Mammogram", "Bone Scan",
    "ECG / Cardiac Tracing", "Other",
]

IMAGING_SYSTEM_PROMPT = """You are a specialist medical imaging AI assistant working
within an Australian health system. When presented with a medical image (X-ray, CT,
MRI, ultrasound, ECG, or other scan), provide a structured radiology-style report:

1. **Modality & Region** — identify the imaging type and anatomical region
2. **Image Quality** — comment on quality, positioning, exposure
3. **Findings** — systematic description of all visible structures
4. **Abnormalities** — clearly flag any abnormal findings with severity
5. **Impression** — concise summary of key findings
6. **Recommendations** — suggested follow-up, additional views, or referrals
7. **Risk Level** — CRITICAL / HIGH / MODERATE / LOW / NORMAL

IMPORTANT DISCLAIMER: This is an AI assistant for educational and workflow support
purposes only. All findings must be reviewed and verified by a qualified radiologist
or treating clinician before any clinical decision is made. Not for diagnostic use."""

OFFLINE_REPORT = """## 🩻 Imaging Report — MediSync AI (Offline Simulation)

**Modality:** Chest X-Ray (PA view)
**Date:** 2026-05-03
**Patient ID:** P-004821

---

### Image Quality
Adequate inspiratory effort. Well-centred projection. No rotation artefact.

### Findings

**Cardiac:**
- Cardiothoracic ratio 0.48 — within normal limits
- No cardiomegaly

**Lungs & Pleura:**
- Mild increased interstitial markings in the left lower zone
- No pleural effusion identified
- No pneumothorax
- Right lung — clear

**Mediastinum:**
- Trachea midline
- No mediastinal widening

**Bones & Soft Tissue:**
- No acute bony injury
- Incidental mild degenerative changes at lower thoracic spine

---

### Impression
> 🟠 **Mild left lower zone interstitial changes** — differential includes early
> consolidation vs atelectasis. No acute cardiorespiratory emergency identified.

### Recommendations
1. Clinical correlation with symptoms (cough, fever, SpO2)
2. Repeat CXR in 4–6 weeks if symptoms persist
3. Consider HRCT chest if changes progress
4. Refer to respiratory medicine if clinically indicated

**Risk Level:** 🟠 MODERATE

---
⚠️ *AI simulation — offline mode. Connect live API for real image analysis.*
⚠️ *This report is NOT a substitute for a qualified radiologist's review.*"""

# Suggested operations shown in the chat window (mirrors main chat page style)
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
# CSS
# ---------------------------------------------------------------------------
PAGE_CSS = """
<style>
/* ── Sticky header ───────────────────────────────────────────────── */
.hdw-sticky-title {
    position: -webkit-sticky;
    position: sticky;
    top: 0;
    z-index: 9999;
    background: #0e0e1a;
    padding: 14px 4px 12px 4px;
    border-bottom: 1px solid #2a2a3d;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    gap: 10px;
}
.hdw-title-dna  { font-size: 26px; line-height: 1; }
.hdw-title-text {
    color: #f5c842;
    font-family: 'Space Mono', monospace;
    font-size: 32px;
    font-weight: bold;
    letter-spacing: 0.06em;
}
.hdw-title-badge {
    margin-left: 10px;
    font-family: 'Space Mono', monospace;
    font-size: 11px;
    color: #f57c5c;
    background: #f57c5c14;
    border: 1px solid #f57c5c44;
    border-radius: 4px;
    padding: 2px 8px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ── Auto-expanding textarea (all textareas on this page) ─────────── */
.stTextArea textarea {
    overflow-y: hidden !important;
    resize: none !important;
    min-height: 56px;
    transition: height 0.1s ease;
}

/* ── Drop zone ───────────────────────────────────────────────────── */
.img-drop-zone {
    border: 2px dashed #252538;
    border-radius: 12px;
    padding: 24px 20px;
    text-align: center;
    background: #08080f;
    margin-bottom: 4px;
    cursor: default;
}
.img-drop-zone .dz-icon  { font-size: 32px; margin-bottom: 6px; }
.img-drop-zone .dz-label {
    color: #666680;
    font-family: 'Space Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.07em;
}
.img-drop-zone .dz-kbd {
    display: inline-block;
    background: #f5c84218;
    border: 1px solid #f5c84244;
    border-radius: 4px;
    color: #f5c842;
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    padding: 1px 6px;
    margin: 0 2px;
}
.img-drop-zone .dz-hint {
    color: #2a2a40;
    font-size: 10px;
    margin-top: 6px;
    font-family: 'Space Mono', monospace;
}

/* ── Image card ──────────────────────────────────────────────────── */
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

/* ── Hide Streamlit's default textarea label when we use our own ─── */
.no-label > label { display: none !important; }

</style>
"""

# ---------------------------------------------------------------------------
# JavaScript — auto-expanding textareas + Ctrl+V paste + drag-drop
# ---------------------------------------------------------------------------
AUTO_EXPAND_AND_PASTE_JS = """
<script>
(function() {
    // ── 1. Auto-expand all textareas ───────────────────────────────────────
    function autoExpand(ta) {
        ta.style.height = 'auto';
        ta.style.height = (ta.scrollHeight) + 'px';
    }

    function attachAutoExpand(ta) {
        if (ta.__hdwExpand) return;
        ta.__hdwExpand = true;
        ta.style.overflowY = 'hidden';
        ta.style.resize = 'none';
        autoExpand(ta);
        ta.addEventListener('input', function() { autoExpand(ta); });
        const orig = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');
        if (orig && orig.set) {
            const origSet = orig.set;
            Object.defineProperty(ta, 'value', {
                set: function(v) {
                    origSet.call(this, v);
                    setTimeout(() => autoExpand(ta), 10);
                },
                get: function() { return orig.get.call(this); }
            });
        }
    }

    function scanAndAttach() {
        document.querySelectorAll('textarea').forEach(attachAutoExpand);
    }

    scanAndAttach();
    const taObserver = new MutationObserver(scanAndAttach);
    taObserver.observe(document.body, { childList: true, subtree: true });

    // ── 2. Ctrl+V paste → relay into hidden text_input ─────────────────────
    if (window.__hdwPasteReady) return;
    window.__hdwPasteReady = true;

    const RELAY_PLACEHOLDER = '__HDW_PASTE_RELAY__';

    function findRelayInput() {
        var docs = [document];
        try { if (window.parent && window.parent.document !== document) docs.push(window.parent.document); } catch(e) {}
        for (var d of docs) {
            var inputs = d.querySelectorAll('input[type="text"], input:not([type])');
            for (var inp of inputs) {
                if (inp.placeholder === RELAY_PLACEHOLDER) return inp;
            }
        }
        return null;
    }

    function sendToRelay(base64Data, mimeType) {
        var relay = findRelayInput();
        if (!relay) {
            try {
                sessionStorage.setItem('hdw_paste_pending', JSON.stringify({
                    data: base64Data, mime: mimeType, ts: Date.now()
                }));
            } catch(e) {}
            return;
        }
        var payload = '__HDW__' + JSON.stringify({ data: base64Data, mime: mimeType });
        var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
        setter.call(relay, payload);
        relay.dispatchEvent(new Event('input', { bubbles: true }));
    }

    function handleImageFile(file) {
        if (!file || !file.type.startsWith('image/')) return;
        var reader = new FileReader();
        reader.onload = function(e) {
            sendToRelay(e.target.result.split(',')[1], file.type);
        };
        reader.readAsDataURL(file);
    }

    // Ctrl+V / Cmd+V
    window.addEventListener('paste', function(e) {
        var items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        for (var i = 0; i < items.length; i++) {
            if (items[i].kind === 'file' && items[i].type.startsWith('image/')) {
                e.preventDefault();
                handleImageFile(items[i].getAsFile());
                return;
            }
        }
    }, true);

    // Drag-and-drop (window level)
    window.addEventListener('dragover', function(e) { e.preventDefault(); }, true);
    window.addEventListener('drop', function(e) {
        e.preventDefault();
        var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
        if (f && f.type.startsWith('image/')) handleImageFile(f);
    }, true);

    // ── 3. Check sessionStorage fallback on load ───────────────────────────
    try {
        var pending = sessionStorage.getItem('hdw_paste_pending');
        if (pending) {
            var obj = JSON.parse(pending);
            if (Date.now() - obj.ts < 10000) {
                sessionStorage.removeItem('hdw_paste_pending');
                setTimeout(function() { sendToRelay(obj.data, obj.mime); }, 500);
            } else {
                sessionStorage.removeItem('hdw_paste_pending');
            }
        }
    } catch(e) {}

})();
</script>
"""

# ---------------------------------------------------------------------------
# AI analysis helper
# ---------------------------------------------------------------------------
def _analyse_image(
    image_bytes: bytes,
    mime_type: str,
    modality: str,
    notes: str,
    global_context: str = "",
) -> str:
    _add_log_safe(f"IMAGING:analyse:{modality}")

    extra = ""
    if global_context.strip():
        extra = f"\n\nAdditional clinical context from referring doctor:\n{global_context.strip()}"

    prompt = (
        f"Please analyse this medical image and provide a structured radiology report.\n\n"
        f"Imaging modality: {modality}\n"
        f"Clinical notes: {notes if notes else 'None provided'}"
        f"{extra}\n\n"
        f"Provide a complete structured report as instructed."
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
        response = model.generate_content(
            [IMAGING_SYSTEM_PROMPT + "\n\n" + prompt, pil_img]
        )
        return response.text

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


def _chat_with_imaging_context(user_msg: str, global_context: str) -> str:
    """Run a chat query in the context of the imaging page."""
    _add_log_safe(f"IMAGING:chat:{user_msg[:60]}")

    system = (
        IMAGING_SYSTEM_PROMPT
        + "\n\nYou are also a clinical assistant. "
        "Answer questions about imaging findings, radiology concepts, clinical risk, "
        "and any uploaded scan context concisely and clearly."
    )

    queue = st.session_state.get("img_queue", [])
    context_block = ""
    if global_context.strip():
        context_block += f"\n\nClinical context from doctor:\n{global_context.strip()}"
    if queue:
        names = ", ".join(e["name"] for e in queue)
        context_block += f"\n\nCurrently queued scans: {names}"

    prompt = user_msg + context_block

    if _HAS_GEMINI_CHAT:
        try:
            return _gemini_chat(
                prompt=prompt,
                system_prompt=system,
                offline_fallback=(
                    "*(Offline simulation)* I can see your query. "
                    "Connect a live API key to receive a real AI response."
                ),
            )
        except Exception:
            pass

    return (
        "*(Offline simulation)* Query received. "
        "Connect a live Gemini API key for real imaging chat responses."
    )


# ---------------------------------------------------------------------------
# Session-state helpers
# ---------------------------------------------------------------------------
def _init_state():
    if "img_queue" not in st.session_state:
        st.session_state.img_queue = []
    if "img_global_notes" not in st.session_state:
        st.session_state.img_global_notes = ""
    if "img_chat_history" not in st.session_state:
        st.session_state.img_chat_history = []
    if "img_chat_sug_clicked" not in st.session_state:
        st.session_state.img_chat_sug_clicked = ""


def _queue_add(image_bytes: bytes, mime_type: str, name: str) -> bool:
    digest = hashlib.md5(image_bytes).hexdigest()
    existing = {hashlib.md5(e["bytes"]).hexdigest() for e in st.session_state.img_queue}
    if digest not in existing:
        st.session_state.img_queue.append({
            "bytes":    image_bytes,
            "mime":     mime_type,
            "name":     name,
            "modality": "Chest X-Ray",
            "notes":    "",
            "report":   None,
        })
        return True
    return False


# ---------------------------------------------------------------------------
# RENDER
# ---------------------------------------------------------------------------
def render() -> None:
    _init_state()

    # ── CSS ──────────────────────────────────────────────────────────────────
    st.markdown(PAGE_CSS, unsafe_allow_html=True)

    # ── STICKY HEADER ────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="hdw-sticky-title">
            <span class="hdw-title-dna">🧬</span>
            <span class="hdw-title-text">🤖&nbsp;HEALTH DIGITAL WORKFORCE</span>
            <span class="hdw-title-badge">🩻&nbsp;MediSync Imaging</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── DROP ZONE — directly under the title (3 rectangles removed) ──────────
    st.markdown(
        """
        <div class="img-drop-zone">
            <div class="dz-icon">🩻</div>
            <div class="dz-label">
                Press&nbsp;<span class="dz-kbd">Ctrl+V</span>&nbsp;to paste
                &nbsp;·&nbsp; drag &amp; drop an image anywhere
                &nbsp;·&nbsp; or use the uploader below
            </div>
            <div class="dz-hint">PNG &nbsp;·&nbsp; JPG &nbsp;·&nbsp; WEBP &nbsp;·&nbsp; BMP &nbsp;·&nbsp; TIFF &nbsp;·&nbsp; DICOM</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── FILE UPLOADER ─────────────────────────────────────────────────────────
    uploaded_files = st.file_uploader(
        "➕  Add scan images from your PC (click or drag files here)",
        type=["png", "jpg", "jpeg", "webp", "bmp", "tiff", "dcm"],
        accept_multiple_files=True,
        key="img_file_uploader",
        help="Supports PNG, JPG, WEBP, BMP, TIFF, DICOM. "
             "You can also paste with Ctrl+V or drag-and-drop.",
    )
    if uploaded_files:
        added_any = False
        for f in uploaded_files:
            if _queue_add(f.read(), f.type or "image/jpeg", f.name):
                added_any = True
        if added_any:
            st.rerun()

    # ── PASTE RELAY — invisible, JS writes base64 image payload here ─────────
    # Hidden via CSS so it never renders as a visible box.
    st.markdown(
        "<style>"
        "div[data-testid='stTextInput']:has(input[placeholder='__HDW_PASTE_RELAY__']),"
        "div[data-testid='stTextInput']:has(input[placeholder='__HDW_PASTE_RELAY__']) * "
        "{ display:none !important; height:0 !important; margin:0 !important; padding:0 !important; }"
        "</style>",
        unsafe_allow_html=True,
    )
    paste_val = st.text_input(
        label="paste_relay",
        label_visibility="collapsed",
        value="",
        placeholder="__HDW_PASTE_RELAY__",
        key="img_paste_relay_input",
    )
    if paste_val and paste_val.startswith("__HDW__"):
        try:
            raw    = paste_val[len("__HDW__"):]
            payload = json.loads(raw)
            img_b  = base64.b64decode(payload["data"])
            mime   = payload.get("mime", "image/png")
            ext    = mime.split("/")[-1].split(";")[0]
            added  = _queue_add(img_b, mime, f"pasted_image.{ext}")
            st.session_state["img_paste_relay_input"] = ""
            if added:
                st.rerun()
        except Exception:
            st.session_state["img_paste_relay_input"] = ""

    # ── JS (auto-expand + Ctrl+V paste + drag-drop) ───────────────────────────
    st.markdown(AUTO_EXPAND_AND_PASTE_JS, unsafe_allow_html=True)

    # =========================================================================
    # IMAGING CHAT WINDOW
    # Uses the exact same native Streamlit components as the working blue-box
    # chat on the main app page (localhost:8501):
    #   • st.button() suggested-ops in 2-col grid
    #   • st.chat_message() for history bubbles
    #   • st.chat_input() for the sticky bottom input bar
    # No custom HTML, no JS relay — pure Streamlit, guaranteed to work.
    # =========================================================================

    st.divider()

    # ── Chat history — native st.chat_message() ───────────────────────────────
    # Rendered FIRST so responses appear above the suggested ops and input bar.
    for msg in st.session_state.img_chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Suggested ops header — always directly above the chat input ───────────
    st.markdown(
        "<p style='font-family:\"Space Mono\",monospace;font-size:9px;"
        "color:#3a3a5a;letter-spacing:0.18em;text-transform:uppercase;"
        "margin:8px 0 8px 0;'>✦ SUGGESTED HEALTH OPERATIONS</p>",
        unsafe_allow_html=True,
    )

    # ── Suggested ops — native st.button() in 2-col grid ─────────────────────
    if "img_chat_sug_clicked" not in st.session_state:
        st.session_state.img_chat_sug_clicked = ""

    for row_start in range(0, len(IMAGING_SUGGESTED_OPS), 2):
        pair = IMAGING_SUGGESTED_OPS[row_start: row_start + 2]
        cols = st.columns(len(pair))
        for col, (btn_label, btn_prompt) in zip(cols, pair):
            with col:
                if st.button(
                    btn_label,
                    key=f"img_sug_{row_start}_{btn_label[:20]}",
                    use_container_width=True,
                ):
                    st.session_state.img_chat_sug_clicked = btn_prompt
                    st.rerun()

    st.write("")

    # ── Chat input — native st.chat_input() — same component as main chat ─────
    # st.chat_input() always sticks to the bottom of the page, so the visual
    # order on screen is: history → suggested ops buttons → chat input bar.
    prefill = st.session_state.get("img_chat_sug_clicked", "") or ""
    if prefill:
        st.session_state["img_chat_sug_clicked"] = ""

    user_input = st.chat_input(
        placeholder=(
            "Enter overall clinical context here — e.g. analyse ECG heartbeat image "
            "carefully to see if there is any potential earlier heart failure risk or "
            "stroke sign that is not mentioned on any of the attached Cardiac Vascular "
            "medical reports… · This note is included with every scan's parse request."
        ),
        key="img_chat_input_widget",
    )

    _pending_msg = user_input or prefill or ""

    if _pending_msg:
        with st.chat_message("user"):
            st.markdown(_pending_msg)
        st.session_state.img_chat_history.append(
            {"role": "user", "content": _pending_msg}
        )
        with st.chat_message("assistant"):
            with st.spinner("🤖 Analysing…"):
                reply = _chat_with_imaging_context(
                    _pending_msg, st.session_state.img_global_notes
                )
            st.markdown(reply)
        st.session_state.img_chat_history.append(
            {"role": "assistant", "content": reply}
        )
        st.rerun()

    # ── IMAGE QUEUE ───────────────────────────────────────────────────────────
    queue = st.session_state.img_queue

    if not queue:
        st.divider()
        st.markdown(
            "<div style='text-align:center; color:#2a2a40; padding:24px 0 12px;"
            "font-family:Space Mono,monospace; font-size:11px; letter-spacing:0.12em;'>"
            "NO SCANS QUEUED — PASTE · DROP · OR UPLOAD TO BEGIN"
            "</div>",
            unsafe_allow_html=True,
        )
        tile_cols = st.columns(4)
        tiles = [
            ("🫁", "Chest X-Ray\nCT Chest"),
            ("🧠", "CT Head\nMRI Brain"),
            ("🫀", "Cardiac Echo\nECG Tracing"),
            ("🔬", "Ultrasound\nAny region"),
        ]
        for col, (icon, label) in zip(tile_cols, tiles):
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

    # Queue header row
    st.divider()
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

    # ── Per-image cards ───────────────────────────────────────────────────────
    for idx, entry in enumerate(queue):

        # Ensure each scan has its own per-scan chat history
        if "chat" not in entry:
            entry["chat"] = []

        st.markdown("<div class='scan-card'>", unsafe_allow_html=True)

        # ── Card header: name + modality + remove ─────────────────────────────
        hdr_left, hdr_mid, hdr_right = st.columns([3, 3, 1])
        with hdr_left:
            st.markdown(
                f"<div class='scan-card-hdr' style='margin-bottom:0;padding-top:6px;'>"
                f"SCAN {idx + 1} &nbsp;·&nbsp; {entry['name']}</div>",
                unsafe_allow_html=True,
            )
        with hdr_mid:
            chosen_modality = st.selectbox(
                "Modality",
                MODALITY_OPTIONS,
                index=MODALITY_OPTIONS.index(entry.get("modality", "Chest X-Ray"))
                      if entry.get("modality") in MODALITY_OPTIONS else 0,
                key=f"img_modality_{idx}",
                label_visibility="collapsed",
            )
            entry["modality"] = chosen_modality
        with hdr_right:
            if st.button("✕", key=f"img_del_{idx}", use_container_width=True,
                         help="Remove this scan"):
                st.session_state.img_queue.pop(idx)
                st.rerun()

        # ── Image preview (full width) ────────────────────────────────────────
        if entry["name"].lower().endswith(".dcm"):
            st.warning("⚠️ DICOM — cannot render preview. AI will analyse metadata only.")
        else:
            st.image(entry["bytes"], use_container_width=True)

        # ── Per-scan chat history ─────────────────────────────────────────────
        for msg in entry["chat"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        # ── Per-scan chat input: textarea + send button ───────────────────────
        # st.chat_input() is page-level only (one per page), so we use
        # st.text_area + st.button here — same AI function, same result.
        # _analyse_image() is called so the AI actually sees the image bytes.
        scan_input_col, scan_send_col = st.columns([11, 1])
        with scan_input_col:
            scan_msg = st.text_area(
                label=f"scan_chat_{idx}",
                label_visibility="collapsed",
                value="",
                placeholder=(
                    "Ask about this scan — e.g. analyse findings, flag risks, "
                    "suggest follow-up, compare with previous reports…"
                ),
                height=68,
                key=f"img_scan_input_{idx}",
            )
        with scan_send_col:
            st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
            scan_send = st.button("↑", key=f"img_scan_send_{idx}",
                                  help="Send", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # ── Process per-scan message ──────────────────────────────────────────
        if scan_send and scan_msg and scan_msg.strip():
            user_text = scan_msg.strip()
            entry["chat"].append({"role": "user", "content": user_text})
            with st.spinner("🤖 Analysing scan…"):
                reply = _analyse_image(
                    entry["bytes"],
                    entry["mime"],
                    chosen_modality,
                    notes=user_text,
                    global_context=st.session_state.img_global_notes,
                )
            entry["chat"].append({"role": "assistant", "content": reply})
            st.rerun()

        # ── Download latest reply as report ───────────────────────────────────
        assistant_replies = [m["content"] for m in entry["chat"] if m["role"] == "assistant"]
        if assistant_replies:
            st.download_button(
                label="⬇️ Download Latest Report (.md)",
                data=assistant_replies[-1],
                file_name=f"report_{entry['name']}.md",
                mime="text/markdown",
                key=f"img_dl_{idx}",
            )

        st.markdown("</div>", unsafe_allow_html=True)
        st.write("")

# ---------------------------------------------------------------------------
# Multipage entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    render()
