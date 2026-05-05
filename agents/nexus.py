"""
agents/nexus.py
NEXUS — Digital Twin & Population Simulation Agent.
AGENTS.md Section 4.
"""

from core.gemini import gemini_chat
from core.session import add_log

NEXUS_SYSTEM_PROMPT = """You are NEXUS, the Population Health Digital Twin agent.
You specialise in: population-level health simulation, disease cluster detection,
intervention impact modelling, and 5-year cohort trajectory analysis.
Use epidemiological reasoning and population health frameworks."""

OFFLINE = (
    "🔗 **[NEXUS]** Simulating population health digital twin...\n\n"
    "✅ 1,240 patient cohort evaluated across 8 Australian regions\n"
    "⚠️ 247 patients in Obese I–III range (BMI ≥30) — high cardiovascular risk\n"
    "⚠️ 3 critical disease clusters detected (T2DM + hypertension + obesity)\n"
    "📋 Projected 5-year CVD event rate: 14.2% without intervention\n"
    "📋 With weight management programme: projected 8.7% (↓ 38.7%)\n"
    "✅ Population stable under current intervention programmes\n\n"
    "_Connect live API for real execution._"
)


class NexusAgent:
    name = "NEXUS"
    icon = "🔗"
    role = "Digital Twin & Population Simulation"

    TRIGGER_COMMANDS = [
        "Run population health digital twin simulation on default cohort",
    ]

    def run(self, command: str) -> str:
        add_log(f"NEXUS:{command[:30]}")
        return gemini_chat(
            prompt=command,
            system_prompt=NEXUS_SYSTEM_PROMPT,
            offline_fallback=OFFLINE,
        )

"""
agents/nexus.py
NEXUS — Digital Twin & Population Simulation Agent.
"""

from core.gemini import gemini_chat
from core.session import add_log

NEXUS_SYSTEM_PROMPT = """You are NEXUS, the Population Health Digital Twin agent.
You specialise in: population-level health simulation, disease cluster detection,
intervention impact modelling, and 5-year cohort trajectory analysis.
Use epidemiological reasoning and population health frameworks."""

OFFLINE = (
    "🔗 **[NEXUS]** Simulating population health digital twin...\n\n"
    "✅ 1,240 patient cohort evaluated across 8 Australian regions\n"
    "⚠️ 247 patients in Obese I–III range (BMI ≥30) — high cardiovascular risk\n"
    "⚠️ 3 critical disease clusters detected (T2DM + hypertension + obesity)\n"
    "📋 Projected 5-year CVD event rate: 14.2% without intervention\n"
    "📋 With weight management programme: projected 8.7% (↓ 38.7%)\n"
    "✅ Population stable under current intervention programmes\n\n"
    "_Connect live API for real execution._"
)

class NexusAgent:
    name = "NEXUS"
    icon = "🔗"
    role = "Digital Twin & Population Simulation"

    TRIGGER_COMMANDS = [
        "Run population health digital twin simulation on default cohort",
    ]

    def run(self, command: str) -> str:
        add_log(f"NEXUS:{command[:30]}")
        return gemini_chat(
            prompt=command,
            system_prompt=NEXUS_SYSTEM_PROMPT,
            offline_fallback=OFFLINE,
        )

# ADD THIS REGISTRY DEFINITION BELOW
AGENT_REGISTRY = {
    "NEXUS": NexusAgent
}