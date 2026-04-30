"""
pages/chat.py
Agent Chat page — Phase 5 (ported from existing app).
AGENTS.md Section 6.
"""

import streamlit as st
from agents import AGENT_REGISTRY
from core.gemini import gemini_chat
from core.session import append_message, get_messages, add_log
from core.config import HEALTH_SYSTEM_PROMPT

OFFLINE_KEYS = {
    agent.TRIGGER_COMMANDS[0]: agent
    for agent in AGENT_REGISTRY.values()
    if agent.TRIGGER_COMMANDS
}

SUGGESTED_OPERATIONS = [
    "Ingest synthetic patient biometric data and run clinical quality checks",
    "Train the XGBoost chronic disease risk model and show AUC score",
    "Run population health digital twin simulation on default cohort",
    "Generate an executive weekly population health report",
    "Run health data compliance scan and rotate the API secret",
    "Predict chronic disease risk for a patient with BMI 38.5, BP 145/92, glucose 6.8",
]


def render() -> None:
    st.markdown("# 💬 Health Digital Workforce Chat")

    # Suggested operations grid
    with st.expander("⭐ SUGGESTED HEALTH OPERATIONS", expanded=True):
        col1, col2 = st.columns(2)
        for i, op in enumerate(SUGGESTED_OPERATIONS):
            col = col1 if i % 2 == 0 else col2
            if col.button(op, use_container_width=True, key=f"op_{i}"):
                _handle_prompt(op)
                st.rerun()

    st.divider()

    # Chat history
    for msg in get_messages():
        css = "user-msg" if msg["role"] == "user" else "agent-msg"
        st.markdown(f'<div class="{css}">{msg["content"]}</div>', unsafe_allow_html=True)

    # Free-text input
    prompt = st.chat_input("Ask about patient health, BMI risks, disease thresholds...")
    if prompt:
        _handle_prompt(prompt)
        st.rerun()


def _handle_prompt(prompt: str) -> None:
    """Route prompt to correct agent or free Gemini chat."""
    append_message("user", prompt)
    add_log(f"CHAT:{prompt[:30]}")

    # Check if it matches an agent trigger command
    for cmd, agent in OFFLINE_KEYS.items():
        if prompt.strip() == cmd:
            reply = agent.run(prompt)
            append_message("assistant", reply)
            return

    # Generic Gemini chat for free-form questions
    reply = gemini_chat(
        prompt=prompt,
        system_prompt=HEALTH_SYSTEM_PROMPT,
        offline_fallback="_No offline response for this query. Connect Gemini API._",
    )
    append_message("assistant", reply)
