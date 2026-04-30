"""
agents/axiom.py
AXIOM — ML Risk Modelling & Disease Prediction Agent.
AGENTS.md Section 4.
"""

from core.gemini import gemini_chat
from core.session import add_log

AXIOM_SYSTEM_PROMPT = """You are AXIOM, the Health ML Risk Modelling agent.
You specialise in: chronic disease risk prediction, interpreting XGBoost model outputs,
analysing patient biometrics (BMI, BP, glucose, HbA1c), and medical imaging findings.
Provide clear risk scores, clinical interpretations, and actionable recommendations."""

OFFLINE_RESPONSES = {
    "model": (
        "🧠 **[AXIOM]** Simulating chronic disease risk model training...\n\n"
        "✅ XGBoost trained on 980 patient samples (80/20 train/test split)\n"
        "📈 AUC Score: **0.934** | Sensitivity: 0.91 | Specificity: 0.88\n"
        "🔑 Top features: BMI (32%) | HbA1c (24%) | Systolic BP (18%) | Age (14%) | Glucose (12%)\n"
        "📉 Log Loss: 0.187 | F1 Score: 0.891\n\n"
        "_Connect live API for real model training._"
    ),
    "predict": (
        "🧠 **[AXIOM]** Predicting chronic disease risk...\n\n"
        "🔴 BMI 38.5 → **Obese Class II** — Metabolic syndrome, severe CVD risk\n"
        "🔴 BP 145/92 → **Stage 2 Hypertension** — Medication + urgent review required\n"
        "🟡 Glucose 6.8 mmol/L → **Pre-diabetic** — Type 2 diabetes risk: HIGH\n"
        "📋 Overall Risk Score: **82/100 — Critical**\n"
        "📋 Recommended: Immediate clinical review, weight management, BP medication\n\n"
        "_Connect live API for real prediction._"
    ),
    "imaging": (
        "🧠 **[AXIOM — MediSync Imaging]** Offline simulation...\n\n"
        "📋 **Findings:** Bilateral lower lobe consolidation present\n"
        "⚠️ **Anomaly Flags:** Possible pleural effusion right base\n"
        "📊 **Confidence Level:** 74% (simulation)\n"
        "📋 **Recommended Follow-up:** CT chest with contrast, respiratory physician review\n"
        "⚠️ *This is a simulation. Not for clinical use.*\n\n"
        "_Connect live API for real imaging analysis._"
    ),
    "default": (
        "🧠 **[AXIOM]** Standing by for risk modelling tasks.\n\n"
        "Available commands:\n"
        "• Train the XGBoost chronic disease risk model and show AUC score\n"
        "• Predict chronic disease risk for a patient with BMI X, BP Y, glucose Z\n"
        "• Analyse medical imaging results\n\n"
        "_Connect live API for real execution._"
    ),
}


class AxiomAgent:
    name = "AXIOM"
    icon = "🧠"
    role = "ML Risk Modelling & Disease Prediction"

    TRIGGER_COMMANDS = [
        "Train the XGBoost chronic disease risk model and show AUC score",
        "Predict chronic disease risk for a patient with BMI 38.5, BP 145/92, glucose 6.8",
    ]

    def run(self, command: str) -> str:
        """Execute an AXIOM command. Never raises an exception."""
        add_log(f"AXIOM:{command[:30]}")
        cmd_lower = command.lower()

        if "train" in cmd_lower or "xgboost" in cmd_lower or "auc" in cmd_lower:
            fallback = OFFLINE_RESPONSES["model"]
        elif "predict" in cmd_lower or "bmi" in cmd_lower or "risk" in cmd_lower:
            fallback = OFFLINE_RESPONSES["predict"]
        elif "imag" in cmd_lower or "xray" in cmd_lower or "scan" in cmd_lower:
            fallback = OFFLINE_RESPONSES["imaging"]
        else:
            fallback = OFFLINE_RESPONSES["default"]

        return gemini_chat(
            prompt=command,
            system_prompt=AXIOM_SYSTEM_PROMPT,
            offline_fallback=fallback,
        )

    def predict_patient_risk(self, bmi: float, systolic: int, glucose: float, age: int = 50) -> str:
        """Generate a clinical risk assessment for individual patient biometrics."""
        prompt = (
            f"Assess chronic disease risk for a patient with:\n"
            f"- BMI: {bmi} kg/m²\n"
            f"- Systolic BP: {systolic} mmHg\n"
            f"- Fasting glucose: {glucose} mmol/L\n"
            f"- Age: {age} years\n\n"
            "Classify each metric, provide an overall risk score out of 100, "
            "and list specific clinical recommendations."
        )
        return gemini_chat(
            prompt=prompt,
            system_prompt=AXIOM_SYSTEM_PROMPT,
            offline_fallback=OFFLINE_RESPONSES["predict"],
        )

    def analyze_imaging(self, image_description: str, image_meta: str) -> str:
        """Generate a diagnostic report from image metadata/description."""
        prompt = (
            f"Analyse this medical image and provide a diagnostic report.\n\n"
            f"Image metadata: {image_meta}\n"
            f"Image description: {image_description}\n\n"
            "Structure your report as: Findings | Anomaly Flags | Confidence Level | "
            "Recommended Follow-up. Include disclaimer that this is AI-assisted, not clinical diagnosis."
        )
        return gemini_chat(
            prompt=prompt,
            system_prompt=AXIOM_SYSTEM_PROMPT,
            offline_fallback=OFFLINE_RESPONSES["imaging"],
        )
