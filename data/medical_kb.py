"""
data/medical_kb.py
Clinical knowledge base — single source of truth for all health thresholds.
Agents import from here. No agent may hardcode clinical values.
AGENTS.md Section 7.
"""

from core.config import (
    BMI_UNDERWEIGHT, BMI_NORMAL_MAX, BMI_OVERWEIGHT,
    BMI_OBESE_I, BMI_OBESE_II, BMI_OBESE_III,
    BMI_BANDS, BMI_DISEASE_MAP, BMI_COLORS,
    BP_NORMAL, BP_ELEVATED, BP_STAGE1, BP_CRISIS,
    BP_STAGES, BP_COLORS,
    GLUCOSE_NORMAL, GLUCOSE_PREDIABETIC,
    GLUCOSE_STAGES, GLUCOSE_COLORS,
    HBA1C_NORMAL, HBA1C_PREDIABETIC,
    RISK_LOW, RISK_MODERATE, RISK_HIGH,
)


def classify_bmi(bmi: float) -> dict:
    """Return band, disease risk, status, and colour for a given BMI."""
    if bmi < BMI_UNDERWEIGHT:
        band, status = "Underweight", "CRITICAL"
    elif bmi < BMI_OVERWEIGHT:
        band, status = "Normal", "OK"
    elif bmi < BMI_OBESE_I:
        band, status = "Overweight", "REVIEW"
    elif bmi < BMI_OBESE_II:
        band, status = "Obese I", "REVIEW"
    elif bmi < BMI_OBESE_III:
        band, status = "Obese II", "CRITICAL"
    else:
        band, status = "Obese III", "CRITICAL"

    return {
        "band":         band,
        "status":       status,
        "disease_risk": BMI_DISEASE_MAP[band],
        "color":        BMI_COLORS[band],
        "risk_score":   round(min(max((bmi - BMI_UNDERWEIGHT) / 40, 0.05), 0.98), 2),
    }


def classify_bp(systolic: int) -> str:
    """Return blood pressure stage label."""
    if systolic < BP_NORMAL:   return "Normal"
    elif systolic < BP_ELEVATED: return "Elevated"
    elif systolic < BP_STAGE1:   return "Stage 1 HTN"
    elif systolic < BP_CRISIS:   return "Stage 2 HTN"
    else:                        return "HTN Crisis"


def classify_glucose(glucose_mmol: float) -> str:
    """Return fasting glucose stage label."""
    if glucose_mmol < GLUCOSE_NORMAL:      return "Normal"
    elif glucose_mmol < GLUCOSE_PREDIABETIC: return "Pre-diabetic"
    else:                                    return "Diabetic"


def classify_hba1c(hba1c_pct: float) -> str:
    """Return HbA1c stage label."""
    if hba1c_pct < HBA1C_NORMAL:      return "Normal"
    elif hba1c_pct < HBA1C_PREDIABETIC: return "Pre-diabetic"
    else:                               return "Diabetic"


def classify_risk(score: float) -> str:
    """Return risk band label from numeric risk score."""
    if score < RISK_LOW:      return "Low"
    elif score < RISK_MODERATE: return "Moderate"
    elif score < RISK_HIGH:     return "High"
    else:                       return "Critical"


# Australian state/territory regions
AU_REGIONS = [
    "New South Wales", "Victoria", "Queensland",
    "Western Australia", "South Australia",
    "Tasmania", "ACT", "Northern Territory",
]

# Common chronic disease ICD-10 codes for reference
ICD10_REFS = {
    "T2DM":         "E11 — Type 2 diabetes mellitus",
    "Hypertension": "I10 — Essential hypertension",
    "Obesity":      "E66 — Obesity",
    "CVD":          "I25 — Chronic ischaemic heart disease",
    "MetSyndrome":  "E88.81 — Metabolic syndrome",
    "SleepApnoea":  "G47.33 — Obstructive sleep apnoea",
}

# Recommended clinical actions by risk level
CLINICAL_ACTIONS = {
    "Low":      "Routine annual health check. Lifestyle advice.",
    "Moderate": "6-month review. Diet & exercise referral. Monitor BP/glucose.",
    "High":     "3-month review. Consider medication. Specialist referral.",
    "Critical": "Immediate clinical review. Urgent intervention required.",
}
