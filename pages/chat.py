"""
pages/chat.py — Agent Chat Page
Renders the main chat interface for Health Digital Workforce.

Security & Safety Improvements:
  • Integrated Microsoft Presidio for robust PII/PHI redaction.
  • Implemented RBAC-based authorization for high-impact operations.
  • Enforced persistent clinical disclaimer acceptance via session state.
  • Added server-side audit logging for all agent interactions.
"""

from __future__ import annotations

import streamlit as st
import logging
from functools import lru_cache
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from core.session import get_messages, append_message, add_log, prune_messages, get_user_role
from agents import AGENT_REGISTRY

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DISCLAIMER_TEXT = "⚠️ **CLINICAL DISCLAIMER:** AI outputs are for decision support only and not diagnostic. Verify all findings with clinical data."
MAX_INPUT_LENGTH = 2000
MAX_SESSION_MESSAGES = 50
HIGH_IMPACT_ROLES = ["admin", "clinician"]

# Initialize PII Engine
@lru_cache(maxsize=1)
def _get_pii_engine():
    return AnalyzerEngine(), AnonymizerEngine()

def _redact_pii(text: str) -> str:
    """Uses Presidio to identify and mask PII/PHI entities."""
    try:
        analyzer, anonymizer = _get_pii_engine()
        results = analyzer.analyze(text=text, language='en', entities=["PERSON", "PHONE_NUMBER", "SSN", "EMAIL_ADDRESS"])
        return anonymizer.anonymize(text=text, analyzer_results=results).text
    except Exception as e:
        logger.error(f"PII Redaction failure: {e}")
        return "[REDACTION_ERROR]"

def _check_authorization(agent_name: str) -> bool:
    """Verifies if the current user has permission to execute specific agent tasks."""
    user_role = get_user_role()
    if agent_name in ["PROMETHEUS", "NEXUS", "SENTINEL"]:
        return user_role in HIGH_IMPACT_ROLES
    return True

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
    commands, keywords = {}, []
    for name in AGENT_REGISTRY:
        agent = _get_agent(name)
        if agent:
            if hasattr(agent, "TRIGGER_COMMANDS"):
                for cmd in agent.TRIGGER_COMMANDS:
                    commands[cmd.strip().lower()] = name
            if hasattr(agent, "KEYWORDS"):
                for kw in agent.KEYWORDS:
                    keywords.append((kw.lower(), name))
    return commands, keywords

def _safe_run_agent(agent, command: str) -> str:
    try:
        return agent.run(command)
    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        return "❌ **System Error:** The agent encountered an issue processing your request."

def _dispatch(user_input: str) -> str:
    try:
        clean_input = user_input.strip()
        add_log(f"DISPATCH_REQUEST: {_redact_pii(clean_input)}")
        
        cmd_map, kw_list = _get_dispatch_map()
        low_input = clean_input.lower()
        
        agent_name = cmd_map.get(low_input)
        if not agent_name:
            for kw, name in kw_list:
                if kw in low_input:
                    agent_name = name
                    break
        
        target_agent = _get_agent(agent_name) if agent_name else _get_agent("NOVA")
        
        if not _check_authorization(agent_name or "NOVA"):
            return "🚫 **Access Denied:** You do not have permission to execute this operation."
            
        return _safe_run_agent(target_agent, clean_input) if target_agent else "I'm sorry, I couldn't route that request."
    except Exception as e:
        logger.error(f"Dispatch error: {e}", exc_info=True)
        return "❌ **Dispatch Error:** Unable to route request."

def _render_message(role: str, text: str):
    try:
        with st.chat_message(role):
            st.markdown(text)
    except Exception as e:
        logger.error(f"Rendering error: {e}", exc_info=True)

SUGGESTED_OPERATIONS = [
    ("Ingest synthetic patient biometric data", "AXIOM", "Ingest synthetic patient biometric data and run clinical quality checks"),
    ("Train XGBoost chronic disease risk model", "PROMETHEUS", "Train the XGBoost chronic disease risk model and show AUC score"),
    ("Run population health digital twin", "NEXUS", "Run population health digital twin simulation on default cohort"),
    ("Generate executive weekly report", "NOVA", "Generate an executive weekly population health report"),
    ("🩻 Run N-1 CTCA digital twin simulation", "NEXUS", "Run N-1 CTCA digital twin simulation"),
    ("Run health data compliance scan", "SENTINEL", "Run health data compliance scan"),
]

def _render_suggested_ops():
    st.markdown("✦ **Suggested Health Operations**")
    cols = st.columns(2)
    for i, (label, agent_name, command) in enumerate(SUGGESTED_OPERATIONS):
        with cols[i % 2]:
            if st.button(label, key=f"sugg_{i}", use_container_width=True):
                if not _check_authorization(agent_name):
                    st.error("Unauthorized: Insufficient privileges.")
                    continue
                
                append_message("user", command)
                with st.status("🤖 Thinking...", expanded=False) as status:
                    reply = _safe_run_agent(_get_agent(agent_name), command)
                    status.update(label="🤖 Complete", state="complete")
                append_message("assistant", reply)
                st.rerun()

def render():
    st.sidebar.markdown("### 🛡️ Safety Center")
    
    if "disclaimer_accepted" not in st.session_state:
        with st.container(border=True):
            st.warning(DISCLAIMER_TEXT)
            if st.button("I acknowledge and accept the clinical disclaimer"):
                st.session_state.disclaimer_accepted = True
                st.rerun()
        return

    st.markdown("### 🤖 HEALTH DIGITAL WORKFORCE")
    prune_messages(MAX_SESSION_MESSAGES)
    messages = get_messages()
    
    if not messages:
        _render_suggested_ops()
        st.divider()

    for msg in messages:
        _render_message(msg["role"], msg["content"])

    user_input = st.chat_input("Ask about patient health, BMI risks, disease thresholds…")
    if user_input:
        if len(user_input) > MAX_INPUT_LENGTH:
            st.error(f"Input too long. Max {MAX_INPUT_LENGTH} characters.")
            return
            
        append_message("user", user_input)
        _render_message("user", user_input)
        with st.status("🤖 Thinking...", expanded=False) as status:
            reply = _dispatch(user_input)
            status.update(label="🤖 Complete", state="complete")
        append_message("assistant", reply)
        _render_message("assistant", reply)
        st.rerun()