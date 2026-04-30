"""
agents/prometheus.py
PROMETHEUS — Reporting, Analytics & Health News Agent.
AGENTS.md Section 4.
"""

from core.gemini import gemini_chat
from core.session import add_log

PROMETHEUS_SYSTEM_PROMPT = """You are PROMETHEUS, the Health Reporting & Analytics agent.
You specialise in: generating executive population health reports, curating medical news,
performing sentiment analysis on clinical notes, and producing trend analytics.
Write in a clear, executive-ready style with data-driven insights."""

OFFLINE_RESPONSES = {
    "report": (
        "📊 **[PROMETHEUS]** Weekly Population Health Report — Week 17, 2026\n\n"
        "📌 Patients monitored: 1,240\n"
        "📌 High-risk patients (BMI ≥30): 247 (↑ 12 from last week)\n"
        "📌 New pre-diabetes flags (glucose 5.6–6.9 mmol/L): 34\n"
        "📌 Stage 2+ Hypertension cases: 41\n"
        "📌 Compliance status: **Green** ✅\n"
        "📌 Interventions recommended this week: 89\n\n"
        "_Connect live API for real report generation._"
    ),
    "news": (
        "📊 **[PROMETHEUS]** AI-Curated Health News (Offline Simulation)\n\n"
        "📰 **Obesity & Metabolic Health:** New GLP-1 receptor agonist trial shows 18% CVD risk reduction\n"
        "📰 **Diabetes Prevention:** Australian NDSS reports 14% increase in pre-diabetes registrations in 2026\n"
        "📰 **Hypertension Management:** PBS listing update for combination BP medications\n"
        "📰 **AI in Healthcare:** CSIRO releases population health AI framework for primary care\n\n"
        "_Connect live API for real-time health news curation._"
    ),
    "default": (
        "📊 **[PROMETHEUS]** Standing by for reporting tasks.\n\n"
        "Available commands:\n"
        "• Generate an executive weekly population health report\n"
        "• Show AI-curated health news\n"
        "• Analyse sentiment of clinical notes\n\n"
        "_Connect live API for real execution._"
    ),
}


class PrometheusAgent:
    name = "PROMETHEUS"
    icon = "📊"
    role = "Reporting, Analytics & Health News"

    TRIGGER_COMMANDS = [
        "Generate an executive weekly population health report",
    ]

    def run(self, command: str) -> str:
        add_log(f"PROMETHEUS:{command[:30]}")
        cmd_lower = command.lower()

        if "report" in cmd_lower or "weekly" in cmd_lower or "executive" in cmd_lower:
            fallback = OFFLINE_RESPONSES["report"]
        elif "news" in cmd_lower or "latest" in cmd_lower:
            fallback = OFFLINE_RESPONSES["news"]
        else:
            fallback = OFFLINE_RESPONSES["default"]

        return gemini_chat(
            prompt=command,
            system_prompt=PROMETHEUS_SYSTEM_PROMPT,
            offline_fallback=fallback,
        )

    def get_health_news(self) -> str:
        """Fetch and summarize latest health news via Gemini."""
        prompt = (
            "Summarize the 4 most important recent developments in:\n"
            "1. Chronic disease management (diabetes, obesity, hypertension)\n"
            "2. AI in Australian healthcare\n"
            "3. Population health policy\n"
            "4. Preventive medicine\n\n"
            "Format each as: **Topic:** Brief summary (2-3 sentences). "
            "Note today's date is April 2026."
        )
        return gemini_chat(
            prompt=prompt,
            system_prompt=PROMETHEUS_SYSTEM_PROMPT,
            offline_fallback=OFFLINE_RESPONSES["news"],
        )

    def analyze_sentiment(self, clinical_text: str) -> str:
        """Perform sentiment and entity analysis on clinical narrative text."""
        prompt = (
            f"Analyse the following clinical note for:\n"
            f"1. Overall sentiment (Positive/Neutral/Concerning/Critical)\n"
            f"2. Key medical entities (conditions, medications, measurements)\n"
            f"3. Urgency indicators\n"
            f"4. Recommended follow-up priority\n\n"
            f"Clinical note:\n{clinical_text[:2000]}"
        )
        return gemini_chat(
            prompt=prompt,
            system_prompt=PROMETHEUS_SYSTEM_PROMPT,
            offline_fallback="⚠️ Sentiment analysis offline. Connect Gemini API.",
        )
