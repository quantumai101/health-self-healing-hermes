"""
pages/imaging.py
MediSync Medical Imaging Analysis page — Phase 7 (P1 feature).
AGENTS.md Section 6.
"""

import streamlit as st
from agents.axiom import AxiomAgent

_axiom = AxiomAgent()


def render() -> None:
    st.markdown("# 🩻 MediSync Imaging")
    st.caption("AI-assisted medical image analysis. For simulation and research purposes only.")

    st.markdown(
        '<div class="disclaimer">⚠️ <strong>DISCLAIMER:</strong> '
        'This is an AI simulation tool. Results are NOT for clinical diagnosis or treatment decisions. '
        'Always consult a qualified medical professional.</div>',
        unsafe_allow_html=True,
    )

    st.info(
        "🚧 **Phase 7 — In Build**\n\n"
        "Full image upload with visual display is being implemented. "
        "Text-based imaging analysis is available now below."
    )

    st.subheader("📋 Imaging Report — Text Description (Preview)")
    image_desc = st.text_area(
        "Describe the imaging findings:",
        height=150,
        placeholder="Chest X-ray showing bilateral infiltrates in lower lobes, possible effusion right base...",
    )
    image_type = st.selectbox("Image Type", ["Chest X-Ray", "CT Scan", "MRI", "Ultrasound", "Other"])

    if st.button("🧠 Generate AXIOM Report", use_container_width=True) and image_desc:
        with st.spinner("AXIOM analysing imaging data..."):
            report = _axiom.analyze_imaging(image_desc, f"Type: {image_type}")
        st.markdown(f'<div class="agent-msg">{report}</div>', unsafe_allow_html=True)
