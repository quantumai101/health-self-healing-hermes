"""
core/chat_widget.py — Reusable bottom chat widget

Drop this into any page's render() function with a single call:

    from core.chat_widget import render_chat_widget
    render_chat_widget(page_key="chat")          # at the END of render()

Each page gets its own isolated chat history, suggested ops, and AI system prompt.
The widget renders:
    1. Chat history  (st.chat_message bubbles)
    2. ✦ SUGGESTED HEALTH OPERATIONS  (2-col st.button grid)
    3. st.chat_input()  (sticky bottom bar)

All state is namespaced by page_key so pages never share history.

KEY FIX: button keys now use numeric col_index instead of label slice,
and inp_key uses page_key only (no session suffix). This prevents
DuplicateWidgetID on first load when Streamlit executes the page script
twice before the session stabilises (observed on HF Spaces + local).
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Safe import of the AI backend
# ---------------------------------------------------------------------------
try:
    from core.gemini import gemini_chat as _gemini_chat
    _HAS_GEMINI = True
except Exception:
    _HAS_GEMINI = False

try:
    from core.session import add_log as _add_log
    _HAS_LOG = True
except Exception:
    _HAS_LOG = False


def _log(msg: str):
    if _HAS_LOG:
        try:
            _add_log(msg)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Per-page suggested operations & system prompts
# ---------------------------------------------------------------------------
_SUGGESTED_OPS: dict[str, list[tuple[str, str]]] = {

    "chat": [
        ("Ingest synthetic patient biometric data and run clinical quality checks",
         "Ingest synthetic patient biometric data and run clinical quality checks"),
        ("Train the XGBoost chronic disease risk model and show AUC score",
         "Train the XGBoost chronic disease risk model and show AUC score"),
        ("Run population health digital twin simulation on default cohort",
         "Run population health digital twin simulation on default cohort"),
        ("Generate an executive weekly population health report",
         "Generate an executive weekly population health report"),
        ("Run health data compliance scan and rotate the API secret",
         "Run health data compliance scan and rotate the API secret"),
        ("Predict chronic disease risk for a patient with BMI 38.5, BP 145/92, glucose 6.8",
         "Predict chronic disease risk for a patient with BMI 38.5, BP 145/92, glucose 6.8"),
        # 7th button — navigates to CTCA Panel View (prefix __NAV__ signals navigation)
        ("🩻 CTCA Report — ZHANG, ZHIMING · ID 350063 · 20/04/2026 · Medscan Merrylands",
         "__NAV__🩻 CTCA Panel View"),
    ],

    "compliance": [
        ("🛡️ Run full HIPAA / Australian Privacy Act compliance scan",
         "Run a full HIPAA and Australian Privacy Act compliance scan on current patient data"),
        ("🔑 Rotate the API secret and log the event",
         "Rotate the API secret, log the rotation event, and confirm the new key is active"),
        ("📋 Generate a compliance audit trail report",
         "Generate a detailed compliance audit trail report for the last 30 days"),
        ("⚠️ Identify and flag any data breach risk indicators",
         "Identify and flag any data breach risk indicators in the current system state"),
        ("🔒 Review data access permissions and highlight anomalies",
         "Review all current data access permissions and highlight any anomalies or over-privileges"),
        ("📊 Produce a monthly compliance dashboard summary",
         "Produce a monthly compliance dashboard summary with pass/fail status for each control"),
    ],

    "dashboard": [
        ("📊 Show population health risk distribution chart",
         "Show the current population health risk distribution chart with breakdown by risk tier"),
        ("🔴 List all HIGH and CRITICAL risk patients",
         "List all patients currently flagged as HIGH or CRITICAL risk with their key indicators"),
        ("📈 Compare this week's metrics vs last week",
         "Compare this week's population health metrics versus last week and highlight changes"),
        ("🧬 Run predictive risk model on the full cohort",
         "Run the predictive chronic disease risk model on the full patient cohort and summarise"),
        ("💊 Identify patients with uncontrolled hypertension",
         "Identify all patients with uncontrolled hypertension (BP > 140/90) in the dashboard"),
        ("📋 Generate an executive health outcomes report",
         "Generate an executive health outcomes report suitable for board presentation"),
    ],

    "ehr_summarizer": [
        ("📄 Summarise the most recent patient EHR",
         "Summarise the most recently loaded patient electronic health record concisely"),
        ("💊 Extract all current medications and dosages",
         "Extract all current medications and dosages from the loaded EHR"),
        ("⚠️ Flag any drug interactions or allergy risks",
         "Flag any potential drug interactions or allergy risks in the current medication list"),
        ("🩺 List all active diagnoses and problem list items",
         "List all active diagnoses and problem list items from the loaded EHR"),
        ("📅 Summarise recent test results and abnormal values",
         "Summarise all recent lab and imaging test results, highlighting any abnormal values"),
        ("📝 Draft a GP referral letter from the EHR data",
         "Draft a professional GP referral letter based on the current patient EHR data"),
    ],

    "news": [
        ("📰 Latest Australian health system news today",
         "What are the latest Australian health system news stories today?"),
        ("🧬 Recent breakthroughs in chronic disease research",
         "Summarise recent breakthroughs in chronic disease research published this week"),
        ("💉 COVID-19 and infectious disease updates",
         "What are the latest COVID-19 and infectious disease updates relevant to Australian clinicians?"),
        ("🏥 Medicare and PBS policy changes this month",
         "Summarise any Medicare and PBS policy changes announced this month"),
        ("🤖 AI in healthcare — latest developments",
         "What are the latest developments in AI applications in healthcare this week?"),
        ("⚕️ Clinical guideline updates from RACGP or AHPRA",
         "Are there any new or updated clinical guidelines from RACGP or AHPRA this month?"),
    ],
}

_SYSTEM_PROMPTS: dict[str, str] = {
    "chat": (
        "You are a Health Digital Workforce AI agent. You help clinicians and health "
        "administrators with population health analytics, chronic disease risk modelling, "
        "patient data quality, and health system operations. Be concise, structured, and "
        "clinically accurate. Always note when outputs are simulated."
    ),
    "compliance": (
        "You are a health data compliance AI specialist. You assist with HIPAA, Australian "
        "Privacy Act, and clinical data governance. Provide structured audit findings, "
        "risk assessments, and actionable remediation steps. Flag critical issues clearly."
    ),
    "dashboard": (
        "You are a population health analytics AI. You interpret health risk dashboards, "
        "patient cohort metrics, chronic disease indicators, and clinical KPIs. Provide "
        "clear, data-driven insights and flag high-risk patterns immediately."
    ),
    "ehr_summarizer": (
        "You are a clinical EHR summarisation AI working in an Australian health setting. "
        "Summarise patient records accurately, extract key clinical data, flag medication "
        "risks, and draft clinical correspondence. Always note AI-generated content."
    ),
    "news": (
        "You are a health news and research AI assistant. You summarise Australian and "
        "global health news, clinical research, policy changes, and guideline updates. "
        "Be accurate, up to date, and clinically relevant."
    ),
}

_PLACEHOLDERS: dict[str, str] = {
    "chat":           "Ask about patient health, BMI risks, disease thresholds…",
    "compliance":     "Ask about compliance status, audit findings, data privacy risks…",
    "dashboard":      "Ask about population health metrics, risk tiers, cohort trends…",
    "ehr_summarizer": "Ask about this patient's EHR — medications, diagnoses, test results…",
    "news":           "Ask about health news, research updates, policy changes…",
}

_OFFLINE_FALLBACK = (
    "*(Offline simulation)* Query received. "
    "Connect a live Gemini API key for real AI responses."
)


# ---------------------------------------------------------------------------
# AI backend
# ---------------------------------------------------------------------------
def _ask_ai(page_key: str, user_msg: str) -> str:
    _log(f"CHAT_WIDGET:{page_key}:{user_msg[:60]}")
    system = _SYSTEM_PROMPTS.get(page_key, _SYSTEM_PROMPTS["chat"])
    if _HAS_GEMINI:
        try:
            return _gemini_chat(
                prompt=user_msg,
                system_prompt=system,
                offline_fallback=_OFFLINE_FALLBACK,
            )
        except Exception:
            pass
    return _OFFLINE_FALLBACK


# ---------------------------------------------------------------------------
# Main render function — call at the END of any page's render()
# ---------------------------------------------------------------------------
def render_chat_widget(page_key: str) -> None:
    """
    Render the bottom chat widget for a given page.

    Args:
        page_key: one of "chat", "compliance", "dashboard",
                  "ehr_summarizer", "news"
    """
    hist_key = f"_cw_history_{page_key}"
    sug_key  = f"_cw_sug_{page_key}"
    inp_key  = f"_cw_input_{page_key}"

    # ── Guard: skip if widgets already registered this script run ────────────
    # Uses a session_state flag keyed to the Streamlit script run counter.
    # Streamlit increments st.session_state._script_run_count internally
    # on every rerun. We read it here (before widget registration) to get
    # the current run number, then stamp "already rendered".
    # This prevents DuplicateWidgetID when Streamlit executes the page
    # script twice on first load (observed on HF Spaces and local multipage).
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        _ctx = get_script_run_ctx()
        # Use a set stored on the context object itself — lives only for
        # this script execution, not persisted in session_state.
        if not hasattr(_ctx, '_cw_rendered_keys'):
            _ctx._cw_rendered_keys = set()
        if inp_key in _ctx._cw_rendered_keys:
            return   # Already rendered this widget set in this run
        _ctx._cw_rendered_keys.add(inp_key)
    except Exception:
        # Fallback if ctx unavailable: use session_state with run counter
        _run_ctr = st.session_state.get("_cw_run_ctr", 0)
        _done_key = f"_cw_done_{page_key}_{_run_ctr}"
        if st.session_state.get(_done_key):
            return
        st.session_state[_done_key] = True
        # Bump counter so next rerun gets a fresh slot
        st.session_state["_cw_run_ctr"] = _run_ctr + 1

    # ── Init session state ────────────────────────────────────────────────────
    if hist_key not in st.session_state:
        st.session_state[hist_key] = []
    if sug_key not in st.session_state:
        st.session_state[sug_key] = ""

    st.divider()

    # ── Chat history ──────────────────────────────────────────────────────────
    for msg in st.session_state[hist_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Suggested ops label ───────────────────────────────────────────────────
    st.markdown(
        "<p style='font-family:\"Space Mono\",monospace;font-size:9px;"
        "color:#3a3a5a;letter-spacing:0.18em;text-transform:uppercase;"
        "margin:8px 0 8px 0;'>✦ SUGGESTED HEALTH OPERATIONS</p>",
        unsafe_allow_html=True,
    )

    # ── Suggested ops — 2-col button grid ─────────────────────────────────────
    # Keys use pure numeric indices (row_start + col_index) — never label
    # slices. Label slices caused collisions when two labels share a prefix.
    ops = _SUGGESTED_OPS.get(page_key, [])
    for row_start in range(0, len(ops), 2):
        pair = ops[row_start: row_start + 2]
        cols = st.columns(len(pair))
        for col_idx, (col, (btn_label, btn_prompt)) in enumerate(zip(cols, pair)):
            with col:
                btn_key = f"_cw_sug_{page_key}_{row_start}_{col_idx}"
                if st.button(
                    btn_label,
                    key=btn_key,
                    use_container_width=True,
                ):
                    # Navigation buttons use __NAV__ prefix
                    if btn_prompt.startswith("__NAV__"):
                        st.session_state["page_selection"] = btn_prompt[7:]
                    else:
                        st.session_state[sug_key] = btn_prompt
                    st.rerun()

    st.write("")

    # ── Chat input ────────────────────────────────────────────────────────────
    prefill = st.session_state.get(sug_key, "") or ""
    if prefill:
        st.session_state[sug_key] = ""

    user_input = st.chat_input(
        placeholder=_PLACEHOLDERS.get(page_key, "Ask anything…"),
        key=inp_key,
    )

    pending = user_input or prefill or ""

    if pending:
        with st.chat_message("user"):
            st.markdown(pending)
        st.session_state[hist_key].append({"role": "user", "content": pending})

        with st.chat_message("assistant"):
            with st.spinner("🤖 Thinking…"):
                reply = _ask_ai(page_key, pending)
            st.markdown(reply)

        st.session_state[hist_key].append({"role": "assistant", "content": reply})
        st.rerun()
