"""pages/compliance.py — Compliance & Audit page stub."""
import streamlit as st
from agents.sentinel import SentinelAgent
_sentinel = SentinelAgent()

def render() -> None:
    st.markdown("# 🛡️ Compliance & Audit")
    st.caption("HIPAA and My Health Record Act compliance monitoring.")
    if st.button("🛡️ Run Full Compliance Scan", use_container_width=True):
        with st.spinner("SENTINEL evaluating compliance rules..."):
            report = _sentinel.generate_compliance_report()
        st.markdown(f'<div class="agent-msg">{report}</div>', unsafe_allow_html=True)
