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

# Configure logging for secure server-side error tracking
logger = logging.getLogger(__name__)

# Constants for data safety
MAX_RENDER_ROWS = 1000
PII_COLUMNS = ["patient_id", "region"]

def require_auth(func: Callable) -> Callable:
    """
    Decorator to enforce authorization. 
    Replaces placeholder logic with a reusable security wrapper.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not st.session_state.get("user_authorized", False):
            st.error("Unauthorized access. Please log in.")
            logger.warning("Unauthorized access attempt blocked.")
            return None
        return func(*args, **kwargs)
    return wrapper

def mask_pii(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies masking to PII columns to prevent accidental exposure.
    """
    masked_df = df.copy()
    for col in PII_COLUMNS:
        if col in masked_df.columns:
            # Mask all but last 4 characters for IDs, or redact entirely
            masked_df[col] = masked_df[col].apply(lambda x: f"***{str(x)[-4:]}" if len(str(x)) > 4 else "***")
    return masked_df

def render() -> None:
    """
    Renders the dashboard with error handling that prevents 
    information disclosure to the end-user.
    """
    try:
        _render_inner()
    except Exception as e:
        logger.error(f"Dashboard rendering error: {traceback.format_exc()}")
        st.error("❌ An unexpected error occurred. Please contact support.")

@require_auth
def _render_inner() -> None:
    """
    Internal rendering logic for the dashboard.
    """
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
        "**DISCLAIMER:** This dashboard is for informational purposes only and does not constitute "
        "medical advice, diagnosis, or treatment. Algorithmic risk scores must be validated by clinical judgment."
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
            
            # Memory safety: check volume
            if len(df) > 50000:
                logger.error(f"Data volume exceeded safety threshold: {len(df)} rows")
                return None

            df["bp_stage"] = df["systolic_bp"].apply(classify_bp)
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
    
    # KPI Row
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Patients", len(df))
    m2.metric("Critical Risk", len(df[df["status"] == "CRITICAL"]))
    m3.metric("BMI ≥ 30", len(df[df["bmi"] >= 30]))
    m4.metric("Diabetic Risk", len(df[df["glucose_stage"] != "Normal"]))
    m5.metric("Stage 2+ HTN", len(df[df["bp_stage"].isin(["Stage 2 HTN", "HTN Crisis"])]))
    st.divider()

    # BMI Table
    band_order = ["Underweight", "Normal", "Overweight", "Obese I", "Obese II", "Obese III"]
    band_counts = df["bmi_band"].value_counts().reindex(band_order, fill_value=0).reset_index()
    band_counts.columns = ["BMI Band", "Patients"]
    band_counts["Disease Risk Triggered"] = band_counts["BMI Band"].map(BMI_DISEASE_MAP)
    st.dataframe(band_counts, use_container_width=True, hide_index=True)

    # Scatter Plot
    fig_bmi = px.scatter(
        df, x="bmi", y="risk_score", size="patients_affected", color="bmi_band",
        hover_data=["systolic_bp", "fasting_glucose_mmol"],
        color_discrete_map=BMI_COLORS, template="plotly_dark"
    )
    st.plotly_chart(fig_bmi, use_container_width=True)

    # Critical Table with Masking
    st.subheader("🚨 High-Risk Patients")
    critical_df = df[df["status"] == "CRITICAL"].sort_values("risk_score", ascending=False)
    
    if len(critical_df) > MAX_RENDER_ROWS:
        st.warning(f"Too many records. Showing first {MAX_RENDER_ROWS}.")
        critical_df = critical_df.head(MAX_RENDER_ROWS)

    # Apply PII masking before display
    masked_critical = mask_pii(critical_df)
    
    st.dataframe(
        masked_critical.rename(columns={
            "patient_id": "Patient ID",
            "age_years": "Age",
            "bmi": "BMI",
            "systolic_bp": "Systolic BP",
            "risk_score": "Risk Score",
            "region": "Region"
        }),
        use_container_width=True,
        hide_index=True
    )

    render_chat_widget(page_key="dashboard")