"""
pages/compliance.py — Compliance & Audit page
"""
import streamlit as st

def render() -> None:
    try:
        _render_inner()
    except Exception as e:
        import traceback
        st.error(f"❌ compliance.py render() crashed: {e}")
        st.code(traceback.format_exc(), language="python")

def _render_inner() -> None:
    from agents.sentinel import SentinelAgent
    from core.chat_widget import render_chat_widget

    _sentinel = SentinelAgent()

    st.markdown("# 🛡️ Compliance & Audit")
    st.caption("HIPAA and My Health Record Act compliance monitoring.")

    if st.button("🛡️ Run Full Compliance Scan", use_container_width=True):
        with st.spinner("SENTINEL evaluating compliance rules..."):
            report = _sentinel.generate_compliance_report()
        st.markdown(f'<div class="agent-msg">{report}</div>', unsafe_allow_html=True)

    render_chat_widget(page_key="compliance")


# Single call — must appear exactly once at module level.
render()
