"""
pages/dashboard.py — Patient Health Risk Dashboard
"""
import streamlit as st
import logging
import traceback
import os
import pandas as pd
from typing import Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)

MAX_RENDER_ROWS = 1000
PII_COLUMNS = ["patient_id", "region"]


def require_auth(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not st.session_state.get("user_authorized", False):
            st.error("Unauthorized access. Please log in.")
            logger.warning("Unauthorized access attempt blocked.")
            return None
        return func(*args, **kwargs)
    return wrapper


def mask_pii(df: pd.DataFrame) -> pd.DataFrame:
    masked_df = df.copy()
    for col in PII_COLUMNS:
        if col in masked_df.columns:
            masked_df[col] = masked_df[col].apply(
                lambda x: f"***{str(x)[-4:]}" if len(str(x)) > 4 else "***"
            )
    return masked_df


def render() -> None:
    try:
        _render_inner()
    except Exception as e:
        logger.error(f"Dashboard rendering error: {traceback.format_exc()}")
        st.error("❌ An unexpected error occurred. Please contact support.")


@require_auth
def _render_inner() -> None:
    import plotly.express as px
    from core.db import get_all_patients
    from data.synthetic_patients import get_mock_df
    from data.medical_kb import classify_bp, classify_glucose
    from core.config import (
        BMI_COLORS, BP_STAGES, BP_COLORS,
        GLUCOSE_STAGES, GLUCOSE_COLORS, BMI_DISEASE_MAP,
    )
    from core.chat_widget import render_chat_widget

    st.warning(
        "**DISCLAIMER:** This dashboard is for informational purposes only and does not "
        "constitute medical advice, diagnosis, or treatment. Algorithmic risk scores must "
        "be validated by clinical judgment."
    )

    @st.cache_data(ttl=3600)
    def _load_df():
        try:
            is_prod = os.getenv("APP_ENV", "development").lower() == "production"
            df = get_all_patients()
            if df is None or len(df) == 0:
                if is_prod:
                    logger.critical("Data source failure in production.")
                    return None
                return get_mock_df()
            if len(df) > 50000:
                logger.error(f"Data volume exceeded safety threshold: {len(df)} rows")
                return None
            df["bp_stage"]      = df["systolic_bp"].apply(classify_bp)
            df["glucose_stage"] = df["fasting_glucose_mmol"].apply(classify_glucose)
            return df
        except Exception as e:
            logger.error(f"Data loading error: {e}")
            return None

    df = _load_df()
    if df is None:
        st.error("Unable to load patient data.")
        return

    st.markdown("# 📊 Patient Health Risk Dashboard")

    # ── KPI Row ───────────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Patients",  len(df))
    m2.metric("Critical Risk",   len(df[df["status"] == "CRITICAL"]))
    m3.metric("BMI ≥ 30",        len(df[df["bmi"] >= 30]))
    m4.metric("Diabetic Risk",   len(df[df["glucose_stage"] != "Normal"]))
    m5.metric("Stage 2+ HTN",    len(df[df["bp_stage"].isin(["Stage 2 HTN", "HTN Crisis"])]))
    st.divider()

    # ── CTCA Digital Twin Simulation button ───────────────────────────────────
    st.markdown("### 🩺 Suggested Health Operations")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Ingest synthetic patient biometric data and run clinical quality checks",
                     use_container_width=True):
            st.session_state["chat_prefill"] = "Ingest synthetic patient biometric data and run clinical quality checks"
        if st.button("Run population health digital twin simulation on default cohort",
                     use_container_width=True):
            st.session_state["chat_prefill"] = "Run population health digital twin simulation on default cohort"
        if st.button("🩺 Run N-1 CTCA digital twin simulation (ZHANG, ZHIMING)",
                     use_container_width=True, type="primary"):
            st.session_state["chat_prefill"] = (
                "Run the N-1 CTCA digital twin simulation for patient ZHANG ZHIMING. "
                "Use the HERMES CTCA report: CAD-RADS 2, pLAD stenosis 17.3%, "
                "pLAD FAI -68.4 HU (borderline elevated), Agatston 50, EF 58.2%. "
                "Provide actionable clinical recommendations."
            )
        if st.button("Predict chronic disease risk for a patient with BMI 38.5, BP 145/92, glucose 6.8",
                     use_container_width=True):
            st.session_state["chat_prefill"] = "Predict chronic disease risk for a patient with BMI 38.5, BP 145/92, glucose 6.8"

    with col2:
        if st.button("Train the XGBoost chronic disease risk model and show AUC score",
                     use_container_width=True):
            st.session_state["chat_prefill"] = "Train the XGBoost chronic disease risk model and show AUC score"
        if st.button("Generate an executive weekly population health report",
                     use_container_width=True):
            st.session_state["chat_prefill"] = "Generate an executive weekly population health report"
        if st.button("Run health data compliance scan and rotate the API secret",
                     use_container_width=True):
            st.session_state["chat_prefill"] = "Run health data compliance scan and rotate the API secret"

    st.divider()

    # ── BMI Table ─────────────────────────────────────────────────────────────
    band_order   = ["Underweight","Normal","Overweight","Obese I","Obese II","Obese III"]
    band_counts  = (df["bmi_band"].value_counts()
                    .reindex(band_order, fill_value=0).reset_index())
    band_counts.columns = ["BMI Band", "Patients"]
    band_counts["Disease Risk Triggered"] = band_counts["BMI Band"].map(BMI_DISEASE_MAP)
    st.dataframe(band_counts, use_container_width=True, hide_index=True)

    # ── Scatter Plot ──────────────────────────────────────────────────────────
    fig_bmi = px.scatter(
        df, x="bmi", y="risk_score",
        size="patients_affected", color="bmi_band",
        hover_data=["systolic_bp", "fasting_glucose_mmol"],
        color_discrete_map=BMI_COLORS, template="plotly_dark"
    )
    st.plotly_chart(fig_bmi, use_container_width=True)

    # ── High-Risk Patients Table ───────────────────────────────────────────────
    st.subheader("🚨 High-Risk Patients")
    critical_df = df[df["status"] == "CRITICAL"].sort_values("risk_score", ascending=False)
    if len(critical_df) > MAX_RENDER_ROWS:
        st.warning(f"Too many records. Showing first {MAX_RENDER_ROWS}.")
        critical_df = critical_df.head(MAX_RENDER_ROWS)

    masked_critical = mask_pii(critical_df)
    st.dataframe(
        masked_critical.rename(columns={
            "patient_id":        "Patient ID",
            "age_years":         "Age",
            "bmi":               "BMI",
            "systolic_bp":       "Systolic BP",
            "risk_score":        "Risk Score",
            "region":            "Region",
        }),
        use_container_width=True,
        hide_index=True,
    )

    render_chat_widget(page_key="dashboard")
