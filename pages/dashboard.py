"""
pages/dashboard.py — Patient Health Risk Dashboard
"""
import streamlit as st


def render() -> None:
    try:
        _render_inner()
    except Exception as e:
        import traceback
        st.error(f"❌ dashboard.py render() crashed: {e}")
        st.code(traceback.format_exc(), language="python")


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

    def _load_df():
        df = get_all_patients()
        if df is None or len(df) < 5:
            df = get_mock_df()
        df["bp_stage"]      = df["systolic_bp"].apply(classify_bp)
        df["glucose_stage"] = df["fasting_glucose_mmol"].apply(classify_glucose)
        return df

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown("# 📊 Patient Health Risk Dashboard")
    st.caption("🏥 Population health biometric data.")

    df = _load_df()

    # ── Top KPI row ──────────────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Patients",        len(df))
    m2.metric("Critical Risk",         len(df[df["status"] == "CRITICAL"]))
    m3.metric("BMI ≥ 30 (Obese)",      len(df[df["bmi"] >= 30]))
    m4.metric("Pre-diabetic/Diabetic", len(df[df["glucose_stage"] != "Normal"]))
    m5.metric("Stage 2+ Hypertension", len(df[df["bp_stage"].isin(["Stage 2 HTN", "HTN Crisis"])]))
    st.divider()

    # ── BMI band table ───────────────────────────────────────────────────────
    band_order = ["Underweight", "Normal", "Overweight", "Obese I", "Obese II", "Obese III"]
    band_counts = (
        df["bmi_band"].value_counts()
          .reindex(band_order, fill_value=0)
          .reset_index()
    )
    band_counts.columns = ["BMI Band", "Patients"]
    band_counts["Disease Risk Triggered"] = band_counts["BMI Band"].map(BMI_DISEASE_MAP)

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Avg BMI",                 f"{df['bmi'].mean():.1f} kg/m²")
    h2.metric("Patients Overweight+",    len(df[df["bmi"] >= 25]))
    h3.metric("Avg Risk Score",          f"{df['risk_score'].mean():.2f}")
    h4.metric("Patients Needing Review", len(df[df["status"].isin(["REVIEW", "CRITICAL"])]))
    st.dataframe(band_counts, use_container_width=True, hide_index=True)
    st.divider()

    # ── BMI vs Risk scatter ──────────────────────────────────────────────────
    st.subheader("📈 BMI vs Risk Score")
    fig_bmi = px.scatter(
        df, x="bmi", y="risk_score",
        size="patients_affected", color="bmi_band",
        hover_data=["patient_id", "region", "systolic_bp", "fasting_glucose_mmol"],
        color_discrete_map=BMI_COLORS, template="plotly_dark", size_max=30,
    )
    for threshold, label in [
        (18.5, "Underweight"), (25, "Overweight"),
        (30, "Obese I"), (35, "Obese II"), (40, "Obese III"),
    ]:
        fig_bmi.add_vline(
            x=threshold, line_dash="dash",
            line_color="rgba(255,255,255,0.3)",
            annotation_text=label, annotation_position="top",
        )
    fig_bmi.update_layout(margin=dict(l=0, r=0, b=0, t=0), paper_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_bmi, use_container_width=True)
    st.divider()

    # ── BP & Glucose side-by-side ────────────────────────────────────────────
    col_left, col_right = st.columns(2)
    with col_left:
        st.subheader("🩺 Blood Pressure Stage Distribution")
        bp_counts = (
            df["bp_stage"].value_counts()
              .reindex(BP_STAGES, fill_value=0)
              .reset_index()
        )
        bp_counts.columns = ["Stage", "Count"]
        fig_bp = px.bar(
            bp_counts, x="Stage", y="Count", color="Stage",
            color_discrete_map=BP_COLORS, template="plotly_dark",
        )
        fig_bp.update_layout(
            showlegend=False,
            margin=dict(l=0, r=0, b=0, t=0),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_bp, use_container_width=True)

    with col_right:
        st.subheader("🩸 Fasting Glucose — Diabetes Risk")
        gluc_counts = (
            df["glucose_stage"].value_counts()
              .reindex(GLUCOSE_STAGES, fill_value=0)
              .reset_index()
        )
        gluc_counts.columns = ["Glucose Stage", "Count"]
        fig_gluc = px.pie(
            gluc_counts, names="Glucose Stage", values="Count",
            color="Glucose Stage",
            color_discrete_map=GLUCOSE_COLORS, template="plotly_dark",
        )
        fig_gluc.update_layout(margin=dict(l=0, r=0, b=0, t=0), paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gluc, use_container_width=True)

    st.divider()

    # ── Critical patients table ──────────────────────────────────────────────
    st.subheader("🚨 High-Risk Patients Requiring Immediate Action")
    critical_df = df[df["status"] == "CRITICAL"].sort_values("risk_score", ascending=False)
    display_cols = [
        "patient_id", "age_years", "bmi", "bmi_band", "systolic_bp",
        "fasting_glucose_mmol", "hba1c_pct", "risk_score", "disease_risk", "region",
    ]
    available = [c for c in display_cols if c in critical_df.columns]
    st.dataframe(
        critical_df[available].head(15).rename(columns={
            "patient_id":           "Patient ID",
            "age_years":            "Age",
            "bmi":                  "BMI",
            "bmi_band":             "BMI Band",
            "systolic_bp":          "Systolic BP",
            "fasting_glucose_mmol": "Glucose (mmol/L)",
            "hba1c_pct":            "HbA1c (%)",
            "risk_score":           "Risk Score",
            "disease_risk":         "Disease Risk",
            "region":               "Region",
        }),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # ── AI Chat window (same as EHR Summarizer) ──────────────────────────────
    render_chat_widget(page_key="dashboard")


# Single call — must appear exactly once at module level.
render()
