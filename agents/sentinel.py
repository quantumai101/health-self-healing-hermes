"""
agents/sentinel.py
SENTINEL — Compliance, Security & Audit Agent.
AGENTS.md Section 4.
"""

from core.gemini import gemini_chat
from core.session import add_log

SENTINEL_SYSTEM_PROMPT = """You are SENTINEL, the Health Compliance & Security agent.
You specialise in: HIPAA compliance, Australian My Health Record Act requirements,
PHI handling policy, API security, and clinical data audit.
Be precise about regulatory requirements and provide clear remediation guidance."""

OFFLINE = (
    "🛡️ **[SENTINEL]** Running health data compliance scan...\n\n"
    "✅ 142 HIPAA / My Health Record compliance rules evaluated\n"
    "✅ All patient data confirmed as synthetic (no real PHI present)\n"
    "✅ API secret rotation completed successfully\n"
    "✅ DuckDB encryption status: enabled\n"
    "⚠️ 2 minor PHI handling policy exceptions logged (non-critical)\n"
    "📋 Compliance Certificate: **GREEN** — valid until next monthly scan\n\n"
    "_Connect live API for real compliance execution._"
)


class SentinelAgent:
    name = "SENTINEL"
    icon = "🛡️"
    role = "Compliance & Security"

    TRIGGER_COMMANDS = [
        "Run health data compliance scan and rotate the API secret",
    ]

    def run(self, command: str) -> str:
        add_log(f"SENTINEL:{command[:30]}")
        return gemini_chat(
            prompt=command,
            system_prompt=SENTINEL_SYSTEM_PROMPT,
            offline_fallback=OFFLINE,
        )

    def generate_compliance_report(self) -> str:
        prompt = (
            "Generate a health data compliance report covering:\n"
            "1. HIPAA key requirements status\n"
            "2. Australian My Health Record Act compliance points\n"
            "3. PHI de-identification verification\n"
            "4. API security posture\n"
            "5. Recommended remediation actions\n\n"
            "Format as a structured compliance certificate with GREEN/AMBER/RED status per section."
        )
        return gemini_chat(
            prompt=prompt,
            system_prompt=SENTINEL_SYSTEM_PROMPT,
            offline_fallback=OFFLINE,
        )
