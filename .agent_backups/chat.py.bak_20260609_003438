"""
pages/chat.py -- Agent Chat Page
Renders the main chat interface for Health Digital Workforce.

Fix (2026-06-07):
  * _render_message routes HTML content through st.components.v1.html()
    so the NEXUS CTCA interactive viewer renders instead of raw markup.
  * SIMULATION ONLY watermark injected into every HTML block.
"""

from __future__ import annotations

import re
import streamlit as st
import streamlit.components.v1 as components
import logging
from functools import lru_cache

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine
    _PRESIDIO_AVAILABLE = True
except ImportError:
    _PRESIDIO_AVAILABLE = False

from core.session import get_messages, append_message, add_log, prune_messages, get_user_role
from agents import AGENT_REGISTRY

# ── Clinical Disclaimer Modal (disclaimer_modal_v2 — TroubleshootAgent) ──────
if "disclaimer_accepted" not in st.session_state:
    st.session_state["disclaimer_accepted"] = False

if not st.session_state["disclaimer_accepted"]:
    # Use CSS to create a centred overlay without st.dialog (Streamlit ≥1.35)
    st.markdown("""
    <style>
    .disclaimer-overlay {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0,0,0,0.75); z-index: 9999;
        display: flex; align-items: center; justify-content: center;
    }
    .disclaimer-box {
        background: #1a1a2e; border: 2px solid #f59e0b;
        border-radius: 16px; padding: 2.5rem 3rem; max-width: 600px;
        text-align: center; color: #fff;
    }
    .disclaimer-box h2 { color: #f59e0b; margin-bottom: 1rem; font-size: 1.4rem; }
    .disclaimer-box p  { font-size: 1rem; line-height: 1.7; color: #d1d5db; }
    </style>
    <div class="disclaimer-overlay">
      <div class="disclaimer-box">
        <h2>⚕ WARNING — CLINICAL DISCLAIMER</h2>
        <p>AI outputs are for <strong>decision support only</strong> and are
        <strong>not diagnostic</strong>. All findings must be verified with
        clinical data by a qualified healthcare professional before any
        clinical action is taken.</p>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("<br>" * 12, unsafe_allow_html=True)
    col_l, col_c, col_r = st.columns([1, 3, 1])
    with col_c:
        if st.button(
            "✓  I acknowledge and accept the clinical disclaimer",
            use_container_width=True,
            type="primary",
            key="clinical_disclaimer_modal_v2_btn",
        ):
            st.session_state["disclaimer_accepted"] = True
            st.rerun()
    st.stop()
# ── End Clinical Disclaimer Modal ─────────────────────────────────────────────


logger = logging.getLogger(__name__)

DISCLAIMER_TEXT = "WARNING **CLINICAL DISCLAIMER:** AI outputs are for decision support only and not diagnostic. Verify all findings with clinical data."
MAX_INPUT_LENGTH = 2000
MAX_SESSION_MESSAGES = 50
HIGH_IMPACT_ROLES = ["admin", "clinician"]
DEFAULT_AGENT = "NOVA"

_SIMULATION_WATERMARK = """
<div style="
    position:fixed; bottom:12px; right:16px; z-index:99999;
    background:rgba(180,0,0,0.82); color:#fff;
    font-family:'Courier New',monospace; font-size:11px; font-weight:bold;
    letter-spacing:2px; padding:4px 12px; border-radius:3px;
    pointer-events:none; user-select:none;
">SIMULATION ONLY -- NOT FOR DIAGNOSTIC USE</div>
<div style="
    position:fixed; top:50%; left:50%;
    transform:translate(-50%,-50%) rotate(-30deg); z-index:99998;
    color:rgba(180,0,0,0.10); font-family:'Courier New',monospace;
    font-size:52px; font-weight:bold; letter-spacing:6px;
    pointer-events:none; user-select:none; white-space:nowrap;
">SIMULATION ONLY</div>
"""

_CTCA_VIEWER_HEIGHT = 640


@lru_cache(maxsize=1)
def _get_pii_engine():
    if not _PRESIDIO_AVAILABLE:
        return None, None
    return AnalyzerEngine(), AnonymizerEngine()


def _redact_pii(text: str) -> str:
    if not _PRESIDIO_AVAILABLE:
        logger.warning("Presidio not available -- PII redaction skipped.")
        return text
    try:
        analyzer, anonymizer = _get_pii_engine()
        results = analyzer.analyze(text=text, language="en",
            entities=["PERSON", "PHONE_NUMBER", "SSN", "EMAIL_ADDRESS"])
        return anonymizer.anonymize(text=text, analyzer_results=results).text
    except Exception as e:
        logger.error(f"PII Redaction failure: {e}")
        raise RuntimeError("PII redaction failed; request blocked for safety.")


def _check_authorization(agent_name: str) -> bool:
    user_role = get_user_role()
    if agent_name in ["PROMETHEUS", "NEXUS", "SENTINEL"]:
        return user_role in HIGH_IMPACT_ROLES
    if agent_name == DEFAULT_AGENT:
        return True
    return False


@lru_cache(maxsize=32)
def _get_agent(name: str):
    try:
        entry = AGENT_REGISTRY.get(name)
        return entry() if isinstance(entry, type) else entry
    except Exception as e:
        logger.error(f"Agent retrieval error for {name}: {e}")
        return None


@lru_cache(maxsize=1)
def _get_dispatch_map():
    commands = {}
    for name in AGENT_REGISTRY:
        agent = _get_agent(name)
        if agent and hasattr(agent, "TRIGGER_COMMANDS"):
            for cmd in agent.TRIGGER_COMMANDS:
                commands[cmd.strip().lower()] = name
    return commands


def _safe_run_agent(agent, command: str) -> str:
    try:
        return agent.run(command)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        return "**System Error:** The agent encountered an issue processing your request."


def _dispatch(user_input: str) -> str:
    try:
        clean_input = user_input.strip()
        try:
            redacted = _redact_pii(clean_input)
            add_log(f"DISPATCH_REQUEST: {redacted}")
        except Exception:
            return "**Security Error:** Unable to process request due to privacy constraints."
        cmd_map = _get_dispatch_map()
        agent_name = cmd_map.get(clean_input.lower(), DEFAULT_AGENT)
        if not _check_authorization(agent_name):
            return "**Access Denied:** You do not have permission to execute this operation."
        target_agent = _get_agent(agent_name)
        if not target_agent:
            return "I'm sorry, I could not route that request."
        return _safe_run_agent(target_agent, clean_input)
    except Exception as e:
        logger.error(f"Dispatch error: {e}", exc_info=True)
        return "**Dispatch Error:** Unable to route request."


def _is_html_content(text: str) -> bool:
    signals = [r'<div\s+id=["\']nexus-', r'<canvas\s', r'<script[\s>]']
    return any(re.search(p, text, re.IGNORECASE) for p in signals)


def _extract_parts(text: str):
    match_start = re.search(r'<div\s+id=["\']nexus-|<canvas\s|<(div|script)\b', text, re.IGNORECASE)
    if not match_start:
        return text, None, ""
    pre  = text[:match_start.start()]
    rest = text[match_start.start():]
    match_end = re.search(r'</script>\s*$', rest, re.IGNORECASE | re.DOTALL)
    if match_end:
        return pre, rest[:match_end.end()], rest[match_end.end():]
    return pre, rest, ""


def _inject_watermark(html: str) -> str:
    if re.search(r'</body>', html, re.IGNORECASE):
        return re.sub(r'</body>', _SIMULATION_WATERMARK + '</body>', html, flags=re.IGNORECASE)
    return html + _SIMULATION_WATERMARK


def _render_message(role: str, text: str):
    try:
        with st.chat_message(role):
            if _is_html_content(text):
                pre, html_block, post = _extract_parts(text)
                if pre.strip():
                    st.markdown(pre)
                if html_block:
                    components.html(_inject_watermark(html_block),
                                    height=_CTCA_VIEWER_HEIGHT, scrolling=False)
                if post.strip():
                    st.markdown(post)
            else:
                st.markdown(text)
    except Exception as e:
        logger.error(f"Rendering error: {e}", exc_info=True)
        try:
            with st.chat_message(role):
                st.markdown(text[:2000] + ("..." if len(text) > 2000 else ""))
        except Exception:
            pass


SUGGESTED_OPERATIONS = [
    ("Ingest synthetic patient biometric data",   "AXIOM",      "Ingest synthetic patient biometric data and run clinical quality checks"),
    ("Train XGBoost chronic disease risk model",  "PROMETHEUS", "Train the XGBoost chronic disease risk model and show AUC score"),
    ("Run population health digital twin",        "NEXUS",      "Run population health digital twin simulation on default cohort"),
    ("Generate executive weekly report",          "NOVA",       "Generate an executive weekly population health report"),
    ("Run N-1 CTCA digital twin simulation",      "NEXUS",      "Run N-1 CTCA digital twin simulation"),
    ("Run health data compliance scan",           "SENTINEL",   "Run health data compliance scan"),
]


def _render_suggested_ops():
    st.markdown("**Suggested Health Operations**")
    cols = st.columns(2)
    for i, (label, agent_name, command) in enumerate(SUGGESTED_OPERATIONS):
        with cols[i % 2]:
            if st.button(label, key=f"chat_sugg_{i}", use_container_width=True):
                if not _check_authorization(agent_name):
                    st.error("Unauthorized: Insufficient privileges.")
                    continue
                append_message("user", command)
                with st.status("Thinking...", expanded=False) as status:
                    reply = _safe_run_agent(_get_agent(agent_name), command)
                    status.update(label="Complete", state="complete")
                append_message("assistant", reply)
                st.rerun()


def render():
    st.sidebar.markdown("### Safety Center")
    if "disclaimer_accepted" not in st.session_state:
        with st.container(border=True):
            st.warning(DISCLAIMER_TEXT)
            
        return

    st.markdown("### HEALTH DIGITAL WORKFORCE")
    prune_messages(MAX_SESSION_MESSAGES)
    messages = get_messages()

    if not messages:
        _render_suggested_ops()
        st.divider()

    for msg in messages:
        _render_message(msg["role"], msg["content"])

    user_input = st.chat_input("Ask about patient health, BMI risks, disease thresholds...")
    if user_input:
        if len(user_input) > MAX_INPUT_LENGTH:
            st.error(f"Input too long. Max {MAX_INPUT_LENGTH} characters.")
            return
        append_message("user", user_input)
        _render_message("user", user_input)
        with st.status("Thinking...", expanded=False) as status:
            reply = _dispatch(user_input)
            status.update(label="Complete", state="complete")
        append_message("assistant", reply)
        _render_message("assistant", reply)
        st.rerun()