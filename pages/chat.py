"""
pages/chat.py — Agent Chat page
Renders the conversation history and handles new user input.

Flow guaranteed by this module:
    1. User message is appended to session state immediately.
    2. st.status "Thinking and reasoning..." is shown while the agent runs.
    3. Assistant reply is appended only after the agent returns.
    4. st.rerun() refreshes the page so all three appear in the correct order.
"""

import streamlit as st
from core.session import append_message, get_messages
from agents import AGENT_REGISTRY

# ---------------------------------------------------------------------------
# Suggested prompts shown at the top of a fresh chat
# ---------------------------------------------------------------------------
SUGGESTIONS = [
    "Ingest synthetic patient biometric data and run clinical quality checks",
    "Train the XGBoost chronic disease risk model and show AUC score",
    "Run population health digital twin simulation on default cohort",
    "Generate an executive weekly population health report",
    "Run health data compliance scan and rotate the API secret",
    "Predict chronic disease risk for a patient with BMI 38.5, BP 145/92, glucose 6.8",
]

# ---------------------------------------------------------------------------
# Helper — pick the best agent for a given command string
# ---------------------------------------------------------------------------
def _route_to_agent(cmd: str) -> str:
    """Return the agent reply for the given command.

    Tries each registered agent's trigger commands first; falls back to the
    first available agent, or returns a static fallback string.
    """
    cmd_lower = cmd.lower()

    # Exact / prefix match against known trigger commands
    for agent in AGENT_REGISTRY.values():
        for trigger in agent.TRIGGER_COMMANDS:
            if trigger.lower() in cmd_lower or cmd_lower in trigger.lower():
                return agent.run(cmd)

    # Default: route to the first agent (usually a general-purpose one)
    if AGENT_REGISTRY:
        first_agent = next(iter(AGENT_REGISTRY.values()))
        return first_agent.run(cmd)

    return "⚠️ No agents are registered. Check your `agents/__init__.py`."


# ---------------------------------------------------------------------------
# Main render function
# ---------------------------------------------------------------------------
def render() -> None:
    st.markdown(
        "<div class='health-topbar-title' style='color:#f5c842;'>◎ HEALTH DIGITAL WORKFORCE CHAT</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    messages = get_messages()

    # ── Suggested operations (only when chat is empty) ──────────────────────
    if not messages:
        st.markdown(
            "<p style='font-size:11px; color:#888899; letter-spacing:0.06em;'>✦ SUGGESTED HEALTH OPERATIONS</p>",
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        for i, suggestion in enumerate(SUGGESTIONS):
            with cols[i % 2]:
                if st.button(suggestion, key=f"sugg_{i}", use_container_width=True):
                    # 1. User message first
                    append_message("user", suggestion)

                    # 2. Thinking indicator while agent works
                    with st.status("🤖 **Thinking and reasoning...**", expanded=False) as status:
                        reply = _route_to_agent(suggestion)
                        status.update(
                            label="✅ Reasoning complete",
                            state="complete",
                            expanded=False,
                        )

                    # 3. Assistant reply after thinking resolves
                    append_message("assistant", reply)
                    st.rerun()

        st.divider()

    # ── Render conversation history ──────────────────────────────────────────
    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Chat input box ───────────────────────────────────────────────────────
    user_input = st.chat_input(
        "Ask about patient health, BMI risks, disease thresholds..."
    )

    if user_input:
        # 1. Show user message immediately
        append_message("user", user_input)
        with st.chat_message("user"):
            st.markdown(user_input)

        # 2. Thinking indicator
        with st.status("🤖 **Thinking and reasoning...**", expanded=False) as status:
            reply = _route_to_agent(user_input)
            status.update(
                label="✅ Reasoning complete",
                state="complete",
                expanded=False,
            )

        # 3. Show and persist the assistant reply
        with st.chat_message("assistant"):
            st.markdown(reply)
        append_message("assistant", reply)
