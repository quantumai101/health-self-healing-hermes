"""pages/news.py — Health News page stub."""
import streamlit as st
from agents.prometheus import PrometheusAgent
_prometheus = PrometheusAgent()

def render() -> None:
    st.markdown("# 📰 AI Health News")
    st.caption("Gemini-curated medical and population health news.")
    if st.button("🔄 Fetch Latest Health News", use_container_width=True):
        with st.spinner("PROMETHEUS curating health news..."):
            news = _prometheus.get_health_news()
        st.markdown(f'<div class="agent-msg">{news}</div>', unsafe_allow_html=True)
    st.divider()
    st.subheader("📝 Clinical Note Sentiment Analysis")
    note = st.text_area("Paste a clinical note for sentiment analysis:", height=150)
    if st.button("🧠 Analyse Sentiment", use_container_width=True) and note:
        with st.spinner("Analysing..."):
            result = _prometheus.analyze_sentiment(note)
        st.markdown(f'<div class="agent-msg">{result}</div>', unsafe_allow_html=True)
