"""
pages/dashboard.py — Patient Health Risk Dashboard
Refactored for HIPAA/GDPR compliance and architectural separation.
"""
import streamlit as st
import logging
import traceback
import os
import pandas as pd
import hashlib
from typing import Optional, Callable
from functools import wraps

# --- Configuration & Constants ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
MAX_RENDER_ROWS = 1000
PII_COLUMNS = ["patient_id", "region"]

# Strict allow-list for chat_prefill to prevent prompt injection/admin abuse
ALLOWED_CHAT_COMMANDS = {
    "ingest_biometrics": "Ingest synthetic patient biometric data and run clinical quality checks",
    "run_simulation": "Run population health digital twin simulation on default cohort",
    "predict_risk": "Predict chronic disease risk for a patient with BMI 38.5, BP 145/92, glucose 6.8",
    "train_model": "Train the XGBoost chronic disease risk model and show AUC score",
    "generate_report": "Generate an executive weekly population health report"
}

# --- Service Layer ---
class PatientDataService:
    """Handles data retrieval and processing logic, decoupled from UI."""
    
    @staticmethod
    def get_processed_data() -> Optional[pd.DataFrame]:
        from core.db import get_all_patients
        from data.synthetic_patients import get_mock_df
        from data.medical_kb import classify_bp, classify_glucose
        
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
            
            # Clinical classification logic (Note: Algorithmic outputs are advisory only)
            df["bp_stage"] = df["systolic_bp"].apply(classify_bp)
            df["glucose_stage"] = df["fasting_glucose_mmol"].apply(classify_glucose)
            return df
        except Exception as e:
            logger.error(f"Data processing error: {e}")
            return None

    @staticmethod
    def pseudonymize(df: pd.DataFrame) -> pd.DataFrame:
        """Robust pseudonymization using HMAC-like hashing to prevent linkage attacks."""
        masked_df = df.copy()
        salt = os.getenv("DATA_SALT")
        
        if not salt:
            if os.getenv("APP_ENV", "").lower() == "production":
                logger.critical("DATA_SALT not set in production environment!")
                raise EnvironmentError("Security configuration missing: DATA_SALT")
            salt = "default_dev_salt"
            
        for col in PII_COLUMNS:
            if col in masked_df.columns:
                masked_df[col] = masked_df[col].apply(
                    lambda x: hashlib.sha256(f"{x}{salt}".encode()).hexdigest()[:12]
                )
        return masked_df

# --- Decorators & Helpers ---
def require_auth(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not st.session_state.get("user_authorized", False):
            st.error("Unauthorized access. Please log in.")
            logger.warning("Unauthorized access attempt blocked.")
            return None
        return func(*args, **kwargs)
    return wrapper

def log_clinical_action(action_name: str):
    """Structured logging for clinical operations triggered via chat."""
    user = st.session_state.get("user_id", "anonymous")
    logger.info(f"CLINICAL_ACTION_TRIGGERED | User: {user} | Action: {action_name}")

# --- UI Rendering ---
def render() -> None:
    try:
        _render_inner()
    except Exception as e:
        logger.error(f"Dashboard rendering error: {traceback.format_exc()}")
        st.error("❌ An unexpected error occurred. Please contact support.")

@require_auth
def _render_inner() -> None:
    import plotly.express as px
    from core.config import BMI_COLORS, BMI_DISEASE_MAP
    from core.chat_widget import render_chat_widget

    st.warning(
        "**DISCLAIMER:** This dashboard is for informational purposes only and does not "
        "constitute medical advice, diagnosis, or treatment. Algorithmic risk scores must "
        "be validated by clinical judgment."
    )

    @st.cache_data(ttl=3600)
    def _load_cached_data():
        return PatientDataService.get_processed_data()

    df = _load_cached_data()
    if df is None:
        st.error("Unable to load patient data.")
        return

    st.markdown("# 📊 Patient Health Risk Dashboard")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Patients", len(df))
    m2.metric("Critical Risk", len(df[df["status"] == "CRITICAL"]))
    m3.metric("BMI ≥ 30", len(df[df["bmi"] >= 30]))
    m4.metric("Diabetic Risk", len(df[df["glucose_stage"] != "Normal"]))
    m5.metric("Stage 2+ HTN", len(df[df["bp_stage"].isin(["Stage 2 HTN", "HTN Crisis"])]))
    st.divider()

    st.markdown("### 🩺 Suggested Health Operations")
    col1, col2 = st.columns(2)
    
    def trigger_action(key: str):
        log_clinical_action(key)
        st.session_state["chat_prefill"] = ALLOWED_CHAT_COMMANDS[key]

    with col1:
        if st.button("Ingest Biometric Data", use_container_width=True):
            trigger_action("ingest_biometrics")
        if st.button("Run Digital Twin Simulation", use_container_width=True):
            trigger_action("run_simulation")
        if st.button("Predict Chronic Risk", use_container_width=True):
            trigger_action("predict_risk")

    with col2:
        if st.button("Train Risk Model", use_container_width=True):
            trigger_action("train_model")
        if st.button("Generate Weekly Report", use_container_width=True):
            trigger_action("generate_report")

    st.divider()

    band_order = ["Underweight","Normal","Overweight","Obese I","Obese II","Obese III"]
    band_counts = (df["bmi_band"].value_counts().reindex(band_order, fill_value=0).reset_index())
    band_counts.columns = ["BMI Band", "Patients"]
    band_counts["Disease Risk Triggered"] = band_counts["BMI Band"].map(BMI_DISEASE_MAP)
    st.dataframe(band_counts, use_container_width=True, hide_index=True)

    # Scatter Plot: Removed PII columns from hover_data to prevent leakage
    fig_bmi = px.scatter(
        df, x="bmi", y="risk_score",
        size="patients_affected", color="bmi_band",
        hover_data={"bmi": True, "risk_score": True, "patients_affected": False},
        color_discrete_map=BMI_COLORS, template="plotly_dark"
    )
    st.plotly_chart(fig_bmi, use_container_width=True)

    st.subheader("🚨 High-Risk Patients")
    critical_df = df[df["status"] == "CRITICAL"].sort_values("risk_score", ascending=False).head(MAX_RENDER_ROWS)
    
    masked_critical = PatientDataService.pseudonymize(critical_df)
    st.dataframe(
        masked_critical.rename(columns={
            "patient_id": "Patient ID",
            "age_years": "Age",
            "bmi": "BMI",
            "systolic_bp": "Systolic BP",
            "risk_score": "Risk Score",
            "region": "Region",
        }),
        use_container_width=True,
        hide_index=True,
    )

    render_chat_widget(page_key="dashboard")