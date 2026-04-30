"""
pages/ehr_summarizer.py
EHR Summarization page — Phase 6 (P1 feature).
AGENTS.md Section 6.
"""

import streamlit as st
from agents.nova import NovaAgent

_nova = NovaAgent()


def render() -> None:
    st.markdown("# 📄 EHR Summarizer")
    st.caption("Upload a patient medical record (PDF or TXT) for AI-powered clinical summarization.")

    st.info(
        "🚧 **Phase 6 — In Build**\n\n"
        "This feature is being implemented. "
        "It will accept PDF/TXT EHR uploads and generate structured clinical summaries via Gemini.\n\n"
        "**Planned sections:** Chief Complaint · Diagnosis · Medications · Lab Results · Risk Flags · Recommended Actions"
    )

    # Preview: text input works today
    st.subheader("📝 Try Text Input (Preview)")
    clinical_text = st.text_area(
        "Paste clinical notes or medical record text:",
        height=200,
        placeholder="Patient presents with chest pain, BP 158/94, glucose 6.8 mmol/L, HbA1c 6.3%...",
    )
    if st.button("🧠 Summarize with NOVA", use_container_width=True) and clinical_text:
        with st.spinner("NOVA analysing clinical text..."):
            summary = _nova.summarize_ehr_text(clinical_text)
        st.markdown(f'<div class="agent-msg">{summary}</div>', unsafe_allow_html=True)
