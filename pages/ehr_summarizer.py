"""
pages/ehr_summarizer.py — EHR Summarizer
"""
import streamlit as st

def render() -> None:
    try:
        _render_inner()
    except Exception as e:
        import traceback
        st.error(f"❌ ehr_summarizer.py render() crashed: {e}")
        st.code(traceback.format_exc(), language="python")

def _render_inner() -> None:
    import io
    from agents.nova import NovaAgent
    from core.session import add_log
    from core.chat_widget import render_chat_widget

    _nova = NovaAgent()

    EXAMPLE_SUMMARY = """🌟 **[NOVA — EHR Summary]**

**Chief Complaint:** Chest pain and shortness of breath on exertion × 3 weeks

**Diagnosis:**
- Primary: Hypertensive heart disease (I11.0)
- Secondary: Type 2 diabetes mellitus, uncontrolled (E11.65)

**Current Medications:**
- Perindopril 10mg daily | Metformin 1000mg BD | Atorvastatin 40mg nocte | Aspirin 100mg daily

**Risk Flags:**
🔴 Stage 2 Hypertension — immediate medication review
🔴 Poorly controlled T2DM (HbA1c 8.1%) — endocrinology referral
🟡 Borderline renal function (eGFR 54) — monitor ACE inhibitor
"""

    DISCLAIMER = """<div style="background:#180800;border:1px solid #f57c5c33;border-radius:6px;
padding:7px 14px;color:#f57c5c;font-size:11px;margin-bottom:14px;">
⚕️ <strong>CLINICAL DISCLAIMER:</strong> AI summary for informational purposes only.
Must be reviewed by a qualified clinician before any clinical decision.
</div>"""

    def _extract_pdf(f):
        try:
            import PyPDF2
            return "".join(p.extract_text() or "" for p in PyPDF2.PdfReader(io.BytesIO(f.read())).pages).strip()
        except Exception as e:
            add_log(f"PDF_ERR:{e}")
            return ""

    def _extract_txt(f):
        try:
            return f.read().decode("utf-8", errors="ignore").strip()
        except Exception as e:
            add_log(f"TXT_ERR:{e}")
            return ""

    st.markdown("# 🏥 EHR Summarizer")
    st.caption("Upload a patient medical record (PDF or TXT) or paste clinical notes for AI summarization via NOVA.")
    st.markdown(DISCLAIMER, unsafe_allow_html=True)

    tab_upload, tab_paste, tab_example = st.tabs([
        "📁 Upload Document", "✏️ Paste Clinical Notes", "📋 See Example Output"
    ])

    raw_text = ""
    source_label = ""

    with tab_upload:
        st.markdown("#### Upload Medical Record")
        # ✅ FIX: unique key prevents duplicate-ID crash on re-render
        uploaded_file = st.file_uploader(
            "Accepted formats: PDF, TXT",
            type=["pdf", "txt"],
            key="ehr_file_uploader_main",
        )
        if uploaded_file:
            file_type = uploaded_file.name.split(".")[-1].lower()
            st.info(f"📎 **{uploaded_file.name}** ({uploaded_file.size:,} bytes)")
            with st.spinner("Extracting text..."):
                raw_text = _extract_pdf(uploaded_file) if file_type == "pdf" else _extract_txt(uploaded_file)
                source_label = f"{file_type.upper()}: {uploaded_file.name}"
            if raw_text:
                with st.expander("📃 View Extracted Text", expanded=False):
                    st.text_area("", raw_text[:3000], height=200, disabled=True)
            else:
                st.warning("⚠️ Could not extract text. Try the Paste tab instead.")

    with tab_paste:
        st.markdown("#### Paste Clinical Notes")
        pasted = st.text_area("Paste any clinical text:", height=280,
            placeholder="Patient: 58yo male\nBP: 162/96 mmHg\nFasting glucose: 8.4 mmol/L...")
        if pasted.strip():
            raw_text = pasted.strip()
            source_label = "Pasted clinical notes"

    with tab_example:
        st.markdown("#### Example AI Summary Output")
        st.markdown(f'<div class="agent-msg">{EXAMPLE_SUMMARY}</div>', unsafe_allow_html=True)

    st.divider()

    if raw_text:
        st.success(f"✅ **{len(raw_text):,} characters** ready — {source_label}")
        col1, col2 = st.columns([3, 1])
        with col1:
            detail_level = st.select_slider("Summary Detail Level",
                options=["Brief", "Standard", "Detailed"], value="Standard")
        with col2:
            focus_area = st.selectbox("Clinical Focus",
                ["General", "Cardiology", "Endocrinology", "Respiratory", "Neurology"])
        if st.button("🧠 Generate NOVA Clinical Summary", use_container_width=True, type="primary"):
            with st.spinner("NOVA analysing..."):
                add_log(f"EHR_SUMMARIZE:{detail_level}/{focus_area}")
                enhanced = f"Detail: {detail_level}\nFocus: {focus_area}\n\n{raw_text[:4000]}"
                summary = _nova.summarize_ehr_text(enhanced)
            st.markdown("#### 📋 AI Clinical Summary")
            st.markdown(f'<div class="agent-msg">{summary}</div>', unsafe_allow_html=True)
            st.download_button("⬇️ Download Summary (.txt)", data=summary,
                file_name=f"ehr_summary_{source_label[:20].replace(' ','_')}.txt", mime="text/plain")
            add_log("EHR_SUMMARY_COMPLETE")
    else:
        st.info("👆 Upload a document or paste clinical notes above to begin.")

    st.divider()
    st.markdown("### 🧠 Clinical Note Sentiment & Entity Analysis")
    sentiment_text = st.text_area("Paste a clinical note for sentiment analysis:", height=120,
        placeholder="Patient appears distressed...", key="sentiment_input")
    if st.button("🔍 Analyse Sentiment & Entities", use_container_width=True) and sentiment_text:
        from agents.prometheus import PrometheusAgent
        with st.spinner("Analysing..."):
            result = PrometheusAgent().analyze_sentiment(sentiment_text)
        st.markdown(f'<div class="agent-msg">{result}</div>', unsafe_allow_html=True)

    render_chat_widget(page_key="ehr_summarizer")


# Single call — render() must appear exactly once at module level.
render()
