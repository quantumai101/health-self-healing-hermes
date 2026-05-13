"""
pages/chat.py — Agent Chat page

Key deduplication approach: render_chat_widget(page_key=...) already namespaces
all button keys under that prefix. The only way duplicates appeared was if
render() was somehow invoked twice in the same Streamlit script execution.

In Streamlit multipage, the page script is the entry point — render() at module
level is called exactly once per rerun. No guard needed. The previous guards were
actively causing the blank-screen regression by blocking re-renders.

This version: no sentinel, no guard, just a clean try/except wrapper.
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

    st.markdown("""
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
""", unsafe_allow_html=True)

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

    # ── Conversation history ───────────────────────────────────────────────
    for msg in get_messages():
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # ── Suggested ops + chat input ─────────────────────────────────────────
    # page_key namespaces all widget keys — prevents collisions with other pages
    render_chat_widget(page_key="chat")


# ── Multipage entrypoint — called once per rerun by Streamlit's router ─────
render()
