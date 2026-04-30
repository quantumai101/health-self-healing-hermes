"""
data/synthetic_patients.py
Synthetic patient biometric data generator.
Produces all columns defined in AGENTS.md Section 9.
All data is synthetic — no real patient data.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
from data.medical_kb import classify_bmi, classify_bp, classify_glucose, AU_REGIONS


def generate_patients(n: int = 120, seed: int = 42) -> pd.DataFrame:
    """
    Generate n synthetic patient records matching the AGENTS.md data contract.
    Returns a pandas DataFrame ready for DuckDB insertion.
    """
    rng = np.random.default_rng(seed)

    # Realistic BMI distribution (Australian population approximation)
    bmi_values = np.concatenate([
        rng.uniform(15.0, 18.4,  int(n * 0.08)),   # Underweight  8%
        rng.uniform(18.5, 24.9,  int(n * 0.33)),   # Normal       33%
        rng.uniform(25.0, 29.9,  int(n * 0.28)),   # Overweight   28%
        rng.uniform(30.0, 34.9,  int(n * 0.17)),   # Obese I      17%
        rng.uniform(35.0, 39.9,  int(n * 0.10)),   # Obese II     10%
        rng.uniform(40.0, 55.0,  int(n * 0.04)),   # Obese III    4%
    ])
    rng.shuffle(bmi_values)
    bmi_values = bmi_values[:n]

    # Derived BP (correlated with BMI)
    bp_base = 110 + (bmi_values - 18.5) * 1.8
    systolic_bp = np.clip(
        bp_base + rng.normal(0, 12, n), 95, 195
    ).astype(int)

    # Derived glucose (correlated with BMI)
    glucose_base = 4.5 + (bmi_values - 18.5) * 0.12
    glucose = np.clip(
        glucose_base + rng.normal(0, 0.8, n), 3.5, 9.5
    ).round(1)

    # HbA1c (correlated with glucose)
    hba1c = np.clip(
        glucose * 0.85 + rng.normal(0, 0.3, n), 4.5, 10.0
    ).round(1)

    # Build classified fields
    bmi_info    = [classify_bmi(b)    for b in bmi_values]
    bp_stages   = [classify_bp(s)     for s in systolic_bp]
    gluc_stages = [classify_glucose(g) for g in glucose]

    # Last review dates (varied over past 3 years)
    today = date.today()
    review_dates = [
        (today - timedelta(days=int(rng.integers(30, 1095)))).strftime("%Y-%m-%d")
        for _ in range(n)
    ]

    records = {
        "patient_id":            [f"PAT-{i:04d}" for i in range(1, n + 1)],
        "age_years":             rng.integers(25, 76, n).tolist(),
        "bmi":                   np.round(bmi_values, 1).tolist(),
        "bmi_band":              [d["band"]         for d in bmi_info],
        "disease_risk":          [d["disease_risk"]  for d in bmi_info],
        "risk_score":            [d["risk_score"]    for d in bmi_info],
        "status":                [d["status"]        for d in bmi_info],
        "region":                rng.choice(AU_REGIONS, n).tolist(),
        "in_high_risk_zone":     rng.choice(["Yes", "No"], n, p=[0.35, 0.65]).tolist(),
        "patients_affected":     rng.integers(1, 11, n).tolist(),
        "systolic_bp":           systolic_bp.tolist(),
        "fasting_glucose_mmol":  glucose.tolist(),
        "hba1c_pct":             hba1c.tolist(),
        "last_review_date":      review_dates,
    }

    df = pd.DataFrame(records)

    # Add derived display columns (not stored in DB, added at query time)
    df["bp_stage"]      = bp_stages
    df["glucose_stage"] = gluc_stages

    return df


def get_mock_df() -> pd.DataFrame:
    """
    Return synthetic DataFrame with all display columns.
    Used as fallback when DuckDB is unavailable.
    """
    return generate_patients()
