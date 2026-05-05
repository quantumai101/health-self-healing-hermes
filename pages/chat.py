"""
pages/chat.py — Agent Chat page
"""
import streamlit as st


def render() -> None:
    try:
        _render_inner()
    except Exception as e:
        import traceback
        st.error(f"❌ chat.py render() crashed: {e}")
        st.code(traceback.format_exc(), language="python")


def _render_inner() -> None:
    from core.session import append_message, get_messages
    from agents import AGENT_REGISTRY
    from core.chat_widget import render_chat_widget

    STICKY_TITLE_CSS = """
<style>
.hdw-sticky-title {
    position: -webkit-sticky;
    position: sticky;
    top: 0;
    z-index: 9999;
    background: #0e0e1a;
    padding: 14px 0 10px 0;
    border-bottom: 1px solid #2a2a3d;
    margin-bottom: 14px;
}
.hdw-sticky-title span {
    color: #f5c842;
    font-family: 'Space Mono', monospace;
    font-size: 32px;
    font-weight: bold;
    letter-spacing: 0.04em;
}
</style>
<div class="hdw-sticky-title">
    <span>🤖 HEALTH DIGITAL WORKFORCE</span>
</div>
"""
    st.markdown(STICKY_TITLE_CSS, unsafe_allow_html=True)

    def _get_instance(entry):
        return entry() if isinstance(entry, type) else entry

    def _route_to_agent(cmd):
        cmd_lower = cmd.lower()
        for entry in AGENT_REGISTRY.values():
            try:
                agent = _get_instance(entry)
                for trigger in getattr(agent, "TRIGGER_COMMANDS", []):
                    if trigger.lower() in cmd_lower or cmd_lower in trigger.lower():
                        return agent.run(cmd)
            except Exception:
                continue
        if AGENT_REGISTRY:
            return _get_instance(next(iter(AGENT_REGISTRY.values()))).run(cmd)
        return "⚠️ No agents available."

    def _send_action(cmd):
        append_message("user", cmd)
        with st.status("🤖 Thinking and reasoning...", expanded=False) as status:
            response_text = _route_to_agent(cmd)
            status.update(label="🤖 Reasoning complete", state="complete", expanded=False)
        append_message("assistant", response_text)
        st.rerun()

    # Conversation history
    for msg in get_messages():
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Suggested ops + chat input
    render_chat_widget(page_key="chat")


# Single call — must appear exactly once at module level.
render()
