"""
pages/news.py — Health News & Clinical Analysis Page
"""
import streamlit as st


def render() -> None:
    try:
        _render_inner()
    except Exception as e:
        import traceback
        st.error(f"❌ news.py render() crashed: {e}")
        st.code(traceback.format_exc(), language="python")


def _render_inner() -> None:
    from agents.prometheus import PrometheusAgent
    from core.chat_widget import render_chat_widget

    _prometheus = PrometheusAgent()

    st.markdown("# 📰 AI Health News")
    st.caption("Gemini-curated medical and population health news.")

    # ✅ unique key prevents StreamlitDuplicateElementId on re-render
    if st.button("🔄 Fetch Latest Health News", use_container_width=True, key="news_fetch_btn"):
        with st.status("🤖 **Thinking and reasoning...** (PROMETHEUS curating news)",
                       expanded=False) as status:
            news = _prometheus.get_health_news()
            status.update(label="✅ News curation complete", state="complete", expanded=False)
        st.markdown(f'<div class="agent-msg">{news}</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("📝 Clinical Note Sentiment Analysis")
    note = st.text_area("Paste a clinical note for sentiment analysis:", height=150,
                        key="news_sentiment_input")
    # ✅ unique key prevents StreamlitDuplicateElementId on re-render
    if st.button("🧠 Analyse Sentiment", use_container_width=True, key="news_sentiment_btn") and note:
        with st.status("🤖 **Thinking and reasoning...** (Analysing clinical sentiment)",
                       expanded=False) as status:
            result = _prometheus.analyze_sentiment(note)
            status.update(label="✅ Analysis complete", state="complete", expanded=False)
        st.markdown(f'<div class="agent-msg">{result}</div>', unsafe_allow_html=True)

    st.divider()
    render_chat_widget(page_key="news")

# ⚠️ DO NOT call render() here — app.py calls it via page routing.
# Calling it here caused StreamlitDuplicateElementId errors.
