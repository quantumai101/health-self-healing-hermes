"""
agents/nova.py
NOVA — Data Ingestion & EHR Quality Agent.
AGENTS.md Section 4.
"""

from core.gemini import gemini_chat
from core.session import add_log

NOVA_SYSTEM_PROMPT = """You are NOVA, the Health Data Ingestion & Quality agent.
You specialise in: loading patient biometric records, running clinical quality checks,
summarizing EHR documents, and validating data completeness.
Be precise, clinical, and flag any anomalies clearly."""

OFFLINE_RESPONSES = {
    "ingest": (
        "🌟 **[NOVA]** Simulating health data ingestion...\n\n"
        "✅ Loaded 1,240 synthetic patient biometric records\n"
        "✅ Clinical quality checks passed (98.2% completeness)\n"
        "⚠️ 22 records flagged for BMI/BP out-of-range review\n"
        "📋 BMI distribution: 8% Underweight | 33% Normal | 28% Overweight | 31% Obese\n"
        "📋 HbA1c flags: 34 pre-diabetic, 11 diabetic thresholds exceeded\n\n"
        "_Connect live API for real execution._"
    ),
    "ehr": (
        "🌟 **[NOVA]** EHR Summary (Offline Simulation)\n\n"
        "**Chief Complaint:** Chest pain and shortness of breath\n"
        "**Diagnosis:** Hypertensive heart disease (I11)\n"
        "**Medications:** Perindopril 5mg, Atorvastatin 40mg, Aspirin 100mg\n"
        "**Lab Results:** BP 158/94 | Glucose 6.2 mmol/L | HbA1c 6.1%\n"
        "**Risk Flags:** 🔴 Stage 2 HTN | 🟡 Pre-diabetic glucose\n"
        "**Recommended Actions:** Medication review, dietitian referral, 3-month follow-up\n\n"
        "_Connect live API for real EHR processing._"
    ),
    "default": (
        "🌟 **[NOVA]** Standing by for data ingestion tasks.\n\n"
        "Available commands:\n"
        "• Ingest synthetic patient biometric data and run clinical quality checks\n"
        "• Upload and summarize an EHR document\n"
        "• Validate patient record completeness\n\n"
        "_Connect live API for real execution._"
    ),
}


class NovaAgent:
    name = "NOVA"
    icon = "🌟"
    role = "Data Ingestion & EHR Quality"

    TRIGGER_COMMANDS = [
        "Ingest synthetic patient biometric data and run clinical quality checks",
    ]

    def run(self, command: str) -> str:
        """
        Execute a NOVA command. Returns offline fallback if Gemini unavailable.
        Never raises an exception.
        """
        add_log(f"NOVA:{command[:30]}")
        cmd_lower = command.lower()

        # Determine offline fallback
        if "ingest" in cmd_lower or "quality" in cmd_lower or "biometric" in cmd_lower:
            fallback = OFFLINE_RESPONSES["ingest"]
        elif "ehr" in cmd_lower or "summar" in cmd_lower or "record" in cmd_lower:
            fallback = OFFLINE_RESPONSES["ehr"]
        else:
            fallback = OFFLINE_RESPONSES["default"]

        return gemini_chat(
            prompt=command,
            system_prompt=NOVA_SYSTEM_PROMPT,
            offline_fallback=fallback,
        )

    def summarize_ehr_text(self, raw_text: str) -> str:
        """Summarize extracted EHR text into structured clinical format."""
        prompt = (
            "Summarize the following medical record into these sections:\n"
            "**Chief Complaint**, **Diagnosis**, **Medications**, **Lab Results**, "
            "**Risk Flags**, **Recommended Actions**.\n\n"
            f"Medical record text:\n{raw_text[:3000]}"
        )
        return gemini_chat(
            prompt=prompt,
            system_prompt=NOVA_SYSTEM_PROMPT,
            offline_fallback=OFFLINE_RESPONSES["ehr"],
        )
