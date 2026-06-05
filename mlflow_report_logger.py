"""
mlflow_report_logger.py
========================
Converts MRA_Analysis_Report items into fully structured MLflow experiment
runs so every finding is queryable, comparable, and visible in the MLflow UI
(http://127.0.0.1:5001).

Usage:
    # After running mra_brain_28May2022.py, run this to push the full report:
    python mlflow_report_logger.py

    # Then open MLflow UI:
    mlflow server --backend-store-uri "sqlite:///I:/MRA Brian 28May2022/brain_mlflow.db" \
                  --host 127.0.0.1 --port 5001

Features:
  • One MLflow run per report section (Vessels, Tissue, WMH, MTA, Morphology, etc.)
  • All numeric findings → mlflow.log_metrics()     (chartable over time)
  • All text findings   → mlflow.log_params()       (searchable/filterable)
  • Rating badges       → mlflow.set_tags()         (filterable by severity)
  • Patient & scan info → mlflow.set_tags()
  • Age auto-calculated from DOB + scan date
  • Confidence labels   → patient-friendly text
  • Brain age delta     → clearly labelled with explanation
  • Runs grouped under "BrainMRI_Analysis" experiment → one row per scan section
"""

import json, os, sys, re
from pathlib import Path
from datetime import datetime

try:
    import mlflow
except ImportError:
    print("ERROR: pip install mlflow"); sys.exit(1)

# ── Config — match your mra_brain_28May2022.py settings ──────────────────────
# Use forward slashes — works on Windows and avoids SQLite URI escape issues
MLFLOW_DB   = "I:/MRA Brian 28May2022/brain_mlflow.db"
REPORT_JSON = "I:/MRA Brian 28May2022/MRA_Analysis_Report_data.json"  # optional

DOB         = "14/03/1955"
SCAN_DATE   = "28 May 2022"
SCAN_TYPE   = "MRA Brain"
FACILITY    = "Castlereagh Imaging"
PATIENT     = "Zhang Zhi Ming"

EXPERIMENT  = "BrainMRI_Analysis"

# ── Patient-friendly confidence labels ────────────────────────────────────────
CONF_LABELS = {
    "high":     "Quantitative (high reliability)",
    "moderate": "Estimated — confirm with MRI if concern",
    "low":      "Approximate — MRA not optimised; recommend MRI",
    "none":     "Not measurable from available images",
}

RATING_LABELS = {
    "🟢": "Normal",
    "🟡": "Mild — monitor",
    "🟠": "Moderate — needs attention",
    "🔴": "Urgent — specialist review",
}

# ─────────────────────────────────────────────────────────────────────────────
def calc_age(dob_str: str, scan_str: str) -> int:
    for fmt in ("%d/%m/%Y", "%d %B %Y", "%d %b %Y", "%Y-%m-%d"):
        try: dob = datetime.strptime(dob_str.strip(), fmt); break
        except: continue
    else: return 0
    for fmt in ("%d %B %Y", "%d/%m/%Y", "%d %b %Y", "%Y-%m-%d"):
        try: scan = datetime.strptime(scan_str.strip(), fmt); break
        except: continue
    else: scan = datetime.now()
    return scan.year - dob.year - ((scan.month, scan.day) < (dob.month, dob.day))

AGE_AT_SCAN = calc_age(DOB, SCAN_DATE)

def _safe_float(v):
    try: return float(str(v).replace("%","").replace("mm","").strip())
    except: return None

def _rating_tag(v):
    sv = str(v)
    for emoji, label in RATING_LABELS.items():
        if emoji in sv: return label
    return ""

def _setup():
    # Forward-slash path works on Windows for SQLite URIs
    db_fwd = MLFLOW_DB.replace("\\", "/")
    uri    = f"sqlite:///{db_fwd}"
    mlflow.set_tracking_uri(uri)
    exp    = mlflow.set_experiment(EXPERIMENT)
    print(f"✅ MLflow URI  → {uri}")
    print(f"   DB file     → {MLFLOW_DB}")
    print(f"   Experiment  → {EXPERIMENT} (id: {exp.experiment_id})")
    print(f"   Patient     → {PATIENT} | DOB: {DOB} | Age at scan: {AGE_AT_SCAN} | Scan: {SCAN_DATE}\n")

# ─────────────────────────────────────────────────────────────────────────────
# BASE TAG SET — common to every run
# ─────────────────────────────────────────────────────────────────────────────
def _base_tags():
    return {
        "patient":      PATIENT,
        "dob":          DOB,
        "age_at_scan":  str(AGE_AT_SCAN),
        "scan_date":    SCAN_DATE,
        "scan_type":    SCAN_TYPE,
        "facility":     FACILITY,
        "report_tool":  "mra_brain_28May2022.py + BrainSkillClient v1.0",
        "mlflow_logger":"mlflow_report_logger.py v2",
    }

# ─────────────────────────────────────────────────────────────────────────────
# SECTION LOGGERS
# ─────────────────────────────────────────────────────────────────────────────

def log_patient_overview():
    """Section 0 — Patient & scan overview."""
    with mlflow.start_run(run_name=f"00_PatientOverview_{SCAN_DATE}"):
        mlflow.set_tags({**_base_tags(),
            "section": "Patient Overview",
            "icon":    "👤",
        })
        mlflow.log_params({
            "patient_name":   PATIENT,
            "date_of_birth":  DOB,
            "age_at_scan":    AGE_AT_SCAN,
            "sex":            "Male",
            "scan_date":      SCAN_DATE,
            "scan_type":      SCAN_TYPE,
            "facility":       FACILITY,
            "known_history":  "BPH, Basilar dolichoectasia, no cardiac disease on CTCA",
        })
        mlflow.log_metrics({"age_at_scan": float(AGE_AT_SCAN)})
    print("  ✓ 00 Patient Overview")


def log_tissue_gm_wm(gm=32.8, wm=18.4, csf=48.8, gm_wm_ratio=1.78,
                      gm_status="MILDLY_REDUCED", confidence="moderate"):
    """Section 1 — Grey & White Matter %."""
    conf_label = CONF_LABELS.get(confidence, confidence)
    # Ratings vs age norms (67yo male)
    gm_rating  = "Normal" if gm >= 40 else ("Mild — monitor" if gm >= 35 else "Moderate — needs attention")
    wm_rating  = "Normal" if wm >= 35 else "Mild — monitor"
    csf_rating = "Normal" if csf <= 20 else ("Mild — monitor" if csf <= 28 else "Moderate — needs attention")

    with mlflow.start_run(run_name=f"01_GreyWhiteMatter_{SCAN_DATE}"):
        mlflow.set_tags({**_base_tags(),
            "section":       "Grey & White Matter",
            "icon":          "🧠",
            "confidence":    conf_label,
            "gm_rating":     gm_rating,
            "wm_rating":     wm_rating,
            "csf_rating":    csf_rating,
            "gm_normal_range": "42–46% (age 67yo male)",
            "wm_normal_range": "40–46%",
            "csf_normal_range":"10–16%",
            "measurement_source": "GMM pixel segmentation on MRA background",
        })
        mlflow.log_params({
            "gm_status":     gm_status,
            "confidence":    conf_label,
            "measurement_note": "MRA not optimised for tissue — confirm with T1 MRI",
        })
        mlflow.log_metrics({
            "grey_matter_pct":  gm,
            "white_matter_pct": wm,
            "csf_pct":          csf,
            "gm_wm_ratio":      gm_wm_ratio,
            "gm_normal_min":    40.0,
            "wm_normal_min":    35.0,
        })
    print(f"  ✓ 01 Grey/White Matter — GM={gm}% WM={wm}% CSF={csf}%")


def log_wmh(wmh_pct=2.73, faz_pv=1, faz_deep=1, burden="MODERATE",
             lacunes=0, confidence="low"):
    """Section 2 — White Matter Hyperintensities / Microvascular Disease."""
    conf_label   = CONF_LABELS.get(confidence, confidence)
    burden_rating = ("Normal" if burden=="NONE" else
                     "Mild — monitor" if burden=="MILD" else
                     "Moderate — needs attention" if burden=="MODERATE" else
                     "Urgent — specialist review")
    with mlflow.start_run(run_name=f"02_WMH_Microvascular_{SCAN_DATE}"):
        mlflow.set_tags({**_base_tags(),
            "section":          "WMH / Microvascular Disease",
            "icon":             "⚡",
            "confidence":       conf_label,
            "wmh_burden":       burden,
            "wmh_rating":       burden_rating,
            "fazekas_pv_grade": str(faz_pv),
            "fazekas_deep_grade": str(faz_deep),
            "fazekas_pv_meaning": (
                "0=None, 1=Punctate (normal/mild), "
                "2=Beginning confluence, 3=Confluent (severe)"),
            "normal_range":     "WMH <2% of WM; Fazekas 0–1 acceptable at age 67",
            "clinical_note":    ("WMH are bright spots in white matter on FLAIR/MRA. "
                                 "Mild WMH is common with age. Moderate/severe increases "
                                 "risk of cognitive decline and stroke."),
            "measurement_source": "Pixel threshold 1.8SD on MRA background",
        })
        mlflow.log_params({
            "wmh_burden":    burden,
            "wmh_rating":    burden_rating,
            "confidence":    conf_label,
            "lacunes":       str(lacunes),
        })
        mlflow.log_metrics({
            "wmh_pct_of_wm":          wmh_pct,
            "fazekas_periventricular": float(faz_pv),
            "fazekas_deep":            float(faz_deep),
            "fazekas_total":           float(faz_pv + faz_deep),
            "lacune_candidates":       float(lacunes),
            "wmh_normal_max":          2.0,
        })
    print(f"  ✓ 02 WMH — {wmh_pct}% | Fazekas PV={faz_pv} Deep={faz_deep} | {burden}")


def log_mta_hippocampus(mta_l=0.0, mta_r=0.0, asym_pct=3.2,
                          hoc_l=93.8, hoc_r=90.8, confidence="low"):
    """Section 3 — MTA Score & Hippocampus."""
    conf_label = CONF_LABELS.get(confidence, confidence)
    mta_max    = max(mta_l, mta_r)
    mta_rating = ("Normal" if mta_max <= 1.5 else
                  "Mild — monitor" if mta_max <= 2.0 else
                  "Moderate — needs attention" if mta_max <= 3.0 else
                  "Urgent — specialist review")
    hoc_min    = min(hoc_l, hoc_r)
    hoc_rating = ("Normal" if hoc_min >= 60 else
                  "Mild — monitor" if hoc_min >= 50 else
                  "Moderate — needs attention")
    asym_rating = "Normal" if asym_pct < 10 else "Mild — monitor"

    with mlflow.start_run(run_name=f"03_MTA_Hippocampus_{SCAN_DATE}"):
        mlflow.set_tags({**_base_tags(),
            "section":          "MTA Score & Hippocampus",
            "icon":             "🏛️",
            "confidence":       conf_label,
            "mta_rating":       mta_rating,
            "hoc_rating":       hoc_rating,
            "asymmetry_rating": asym_rating,
            "mta_normal_range": "≤1.5 at age 67 (Scheltens scale)",
            "hoc_normal_range": ">60%",
            "asym_normal_range":"<10% L vs R",
            "mta_scale_note":   ("0=No atrophy, 1=Minimal, 2=Mild, "
                                 "3=Moderate, 4=Severe. "
                                 "Hippocampus is key memory structure — "
                                 "shrinkage is early Alzheimer marker."),
            "hoc_note":         ("HOC = Hippocampal Occupancy %. "
                                 ">60% = normal. <50% = high risk. "
                                 "L vs R asymmetry >10% needs investigation."),
            "measurement_source":"Temporal ROI pixel analysis on MRA axial slices",
            "clinical_note":    "Best assessed with dedicated coronal T1 MRI",
        })
        mlflow.log_params({
            "mta_interpretation": mta_rating,
            "hoc_interpretation": hoc_rating,
            "confidence":         conf_label,
            "recommended_sequence": "Dedicated coronal T1 MRI for true MTA scoring",
        })
        mlflow.log_metrics({
            "mta_proxy_left":    mta_l,
            "mta_proxy_right":   mta_r,
            "mta_asymmetry_pct": asym_pct,
            "hoc_estimate_left":  hoc_l,
            "hoc_estimate_right": hoc_r,
            "hoc_asymmetry_pct": abs(hoc_l - hoc_r),
            "mta_normal_max":    1.5,
            "hoc_normal_min":    60.0,
        })
    print(f"  ✓ 03 MTA — L={mta_l} R={mta_r} | HOC L={hoc_l}% R={hoc_r}% | Asym={asym_pct}%")


def log_morphology(atrophy_grade=2, sulcal="mild", ventricles="normal",
                    brain_age_delta=9.0, confidence="low"):
    """Section 4 — Cortical Morphology & Brain Age."""
    conf_label    = CONF_LABELS.get(confidence, confidence)
    atrophy_rating = ("Normal" if atrophy_grade <= 1 else
                      "Mild — monitor" if atrophy_grade == 2 else
                      "Moderate — needs attention")
    # Brain age delta explanation
    age_at_scan   = AGE_AT_SCAN
    estimated_brain_age = age_at_scan + brain_age_delta
    delta_direction = ("older-appearing" if brain_age_delta > 0
                       else "younger-appearing" if brain_age_delta < 0
                       else "same as chronological age")
    age_rating = ("Normal" if abs(brain_age_delta) <= 5 else
                  "Mild — monitor" if abs(brain_age_delta) <= 10 else
                  "Moderate — needs attention")

    with mlflow.start_run(run_name=f"04_CorticalMorphology_{SCAN_DATE}"):
        mlflow.set_tags({**_base_tags(),
            "section":             "Cortical Morphology & Brain Age",
            "icon":                "🔬",
            "confidence":          conf_label,
            "atrophy_rating":      atrophy_rating,
            "brain_age_rating":    age_rating,
            "sulcal_widening":     sulcal,
            "ventricular_size":    ventricles,
            "atrophy_scale":       "0=None, 1=Mild, 2=Moderate, 3=Severe",
            "brain_age_delta_explanation": (
                f"+{brain_age_delta:.1f}yr means brain pixel morphology "
                f"(sulcal width, CSF spaces) resembles a person aged "
                f"~{estimated_brain_age:.0f}, which is {brain_age_delta:.0f} years "
                f"{delta_direction} than your actual scan age of {age_at_scan}. "
                "This does NOT mean brain damage — needs T1 MRI confirmation."
            ),
            "normal_range":        "Atrophy grade 0–1; brain age delta ±5yr acceptable",
            "measurement_source":  "Sulcal CSF fraction + ventricular CSF on MRA",
            "clinical_note":       "Confirm with dedicated T1 MPRAGE MRI",
        })
        mlflow.log_params({
            "atrophy_grade":          str(atrophy_grade),
            "atrophy_rating":         atrophy_rating,
            "sulcal_widening":        sulcal,
            "ventricular_size":       ventricles,
            "brain_age_rating":       age_rating,
            "delta_direction":        delta_direction,
            "confidence":             conf_label,
            "chronological_age_at_scan": str(age_at_scan),
            "estimated_brain_age":    f"~{estimated_brain_age:.0f} years",
        })
        mlflow.log_metrics({
            "atrophy_grade":          float(atrophy_grade),
            "brain_age_delta_years":  brain_age_delta,
            "estimated_brain_age":    estimated_brain_age,
            "chronological_age":      float(age_at_scan),
            "brain_age_delta_abs":    abs(brain_age_delta),
            "normal_delta_max":       5.0,
        })
    print(f"  ✓ 04 Morphology — Grade={atrophy_grade} | BrainAgeDelta={brain_age_delta:+.1f}yr → brain appears ~{estimated_brain_age:.0f}yo")


def log_cerebrovascular(basilar_mm=None, dolichoectasia="mild",
                          circle_of_willis="complete", missing_segments=None,
                          stenosis=False, aneurysm=False,
                          overall="abnormal", confidence="moderate"):
    """Section 5 — Cerebrovascular / MRA Vessels."""
    conf_label = CONF_LABELS.get(confidence, confidence)
    basil_rating = ("Normal" if dolichoectasia=="none" else
                    "Mild — monitor" if dolichoectasia=="mild" else
                    "Moderate — needs attention" if dolichoectasia=="moderate" else
                    "Urgent — specialist review")
    cow_rating = "Normal" if circle_of_willis=="complete" else "Mild — monitor"

    with mlflow.start_run(run_name=f"05_Cerebrovascular_{SCAN_DATE}"):
        tags = {**_base_tags(),
            "section":              "Cerebrovascular / MRA Vessels",
            "icon":                 "🩸",
            "confidence":           conf_label,
            "basilar_rating":       basil_rating,
            "circle_of_willis":     circle_of_willis,
            "cow_rating":           cow_rating,
            "stenosis_detected":    str(stenosis),
            "aneurysm_detected":    str(aneurysm),
            "overall_vasculature":  overall,
            "dolichoectasia_note":  ("Basilar dolichoectasia = tortuous/enlarged basilar artery. "
                                     "Mild = monitor annually. Moderate/severe = neurology referral."),
            "cow_note":             ("Circle of Willis connects brain arteries — "
                                     "incomplete variants are common (20–30% of people) "
                                     "and usually benign but increase stroke risk if stenosis occurs."),
            "clinical_note":        "Baseline study — compare all future MRA to this scan",
        }
        if missing_segments:
            tags["missing_cow_segments"] = ", ".join(missing_segments)
        mlflow.set_tags(tags)

        params = {
            "dolichoectasia":       dolichoectasia,
            "circle_of_willis":     circle_of_willis,
            "stenosis_detected":    str(stenosis),
            "aneurysm_detected":    str(aneurysm),
            "overall_vasculature":  overall,
            "confidence":           conf_label,
            "baseline_note":        "28 May 2022 MRA is the reference for future comparison",
        }
        if missing_segments:
            params["missing_segments"] = ", ".join(missing_segments)
        mlflow.log_params(params)

        metrics = {
            "stenosis_flag":    float(stenosis),
            "aneurysm_flag":    float(aneurysm),
            "dolichoectasia_severity": (
                0 if dolichoectasia=="none" else
                1 if dolichoectasia=="mild" else
                2 if dolichoectasia=="moderate" else 3
            ),
        }
        if basilar_mm:
            metrics["basilar_artery_mm"] = float(basilar_mm)
            metrics["basilar_normal_max"] = 4.5
        mlflow.log_metrics(metrics)
    print(f"  ✓ 05 Cerebrovascular — Basilar: {dolichoectasia} | CoW: {circle_of_willis} | Stenosis: {stenosis}")


def log_overall_rating(rating="FAIR", emoji="🟡", rationale="",
                        top_findings=None, recommendations=None):
    """Section 6 — Overall SENTINEL Rating & Recommendations."""
    with mlflow.start_run(run_name=f"06_OverallRating_{SCAN_DATE}"):
        mlflow.set_tags({**_base_tags(),
            "section":         "Overall SENTINEL Rating",
            "icon":            "🛡️",
            "overall_rating":  rating,
            "overall_emoji":   emoji,
            "rating_scale":    "EXCELLENT > GOOD > FAIR > CONCERNING > CRITICAL",
        })
        params = {
            "overall_rating": rating,
            "rationale":      (rationale or "")[:500],
        }
        if top_findings:
            for i, f in enumerate(top_findings[:5], 1):
                params[f"finding_{i}"] = str(f)[:200]
        if recommendations:
            for i, r in enumerate(recommendations[:5], 1):
                params[f"recommendation_{i}"] = str(r)[:200]
        mlflow.log_params(params)
        mlflow.log_metrics({
            "overall_score": (
                5 if rating=="EXCELLENT" else
                4 if rating=="GOOD" else
                3 if rating=="FAIR" else
                2 if rating=="CONCERNING" else 1
            )
        })
    print(f"  ✓ 06 Overall Rating — {emoji} {rating}")


def log_scan_metadata():
    """Section 7 — Scan technical metadata for audit trail."""
    with mlflow.start_run(run_name=f"07_ScanMetadata_{SCAN_DATE}"):
        mlflow.set_tags({**_base_tags(),
            "section":   "Scan Technical Metadata",
            "icon":      "📋",
        })
        mlflow.log_params({
            "dicom_source":     r"I:\MRA Brian 28May2022",
            "output_html":      r"I:\MRA Brian 28May2022\MRA_Analysis_Report.html",
            "output_txt":       r"I:\MRA Brian 28May2022\MRA_Analysis_Report.txt",
            "mlflow_db":        MLFLOW_DB,
            "ai_model":         "gemini-2.5-flash",
            "ml_segmentation":  "GMM 3-component + multi-Otsu + morphological",
            "ml_version":       "BrainSkillClient v1.0",
            "report_version":   "mra_brain_28May2022.py v3",
            "age_calculation":  f"Auto from DOB {DOB} + scan {SCAN_DATE} = {AGE_AT_SCAN} yr",
            "next_mra_due":     "May 2023 (12-month basilar monitoring)",
        })
        mlflow.log_metrics({
            "age_at_scan_years": float(AGE_AT_SCAN),
        })
    print(f"  ✓ 07 Scan Metadata logged")


# ─────────────────────────────────────────────────────────────────────────────
# LOAD FROM JSON (if mra_brain script saved results)
# ─────────────────────────────────────────────────────────────────────────────

def load_results_from_json(json_path: str) -> dict:
    """Try to load analysis results from JSON saved by main script."""
    try:
        p = Path(json_path)
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            print(f"  📂 Loaded results from {json_path}")
            return data
    except Exception as e:
        print(f"  ⚠️  Could not load {json_path}: {e}")
    return {}


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*65}")
    print(f"  📊 MLflow Report Logger — MRA Brain {SCAN_DATE}")
    print(f"  Patient: {PATIENT} | DOB: {DOB} | Age at scan: {AGE_AT_SCAN}")
    print(f"  MLflow DB: {MLFLOW_DB}")
    print(f"{'='*65}\n")

    _setup()

    # Try to load actual results from JSON; fall back to values from HTML report
    results = load_results_from_json(REPORT_JSON)

    # ── Extract values from results if available, else use HTML report values ──
    ml_tissue = results.get("_ml_pixel_analysis", {}).get("tissue", {})
    ml_wmh    = results.get("_ml_pixel_analysis", {}).get("wmh",    {})
    ml_mta    = results.get("_ml_pixel_analysis", {}).get("mta",    {})
    ml_morph  = results.get("_ml_pixel_analysis", {}).get("morph",  {})

    print("Logging all report sections to MLflow...\n")

    # Section 0 — Patient Overview
    log_patient_overview()

    # Section 1 — Grey & White Matter
    log_tissue_gm_wm(
        gm          = ml_tissue.get("grey_matter_pct",  32.8),
        wm          = ml_tissue.get("white_matter_pct", 18.4),
        csf         = ml_tissue.get("csf_pct",          48.8),
        gm_wm_ratio = ml_tissue.get("gm_wm_ratio",      1.78),
        gm_status   = ml_tissue.get("notes", "").split("GM status:")[1].split(".")[0].strip()
                      if "GM status:" in ml_tissue.get("notes","") else "MILDLY_REDUCED",
        confidence  = ml_tissue.get("confidence", "moderate"),
    )

    # Section 2 — WMH / Microvascular
    log_wmh(
        wmh_pct    = ml_wmh.get("wmh_pct_of_wm",           2.73),
        faz_pv     = int(ml_wmh.get("fazekas_periventricular", 1)),
        faz_deep   = int(ml_wmh.get("fazekas_deep",            1)),
        burden     = ml_wmh.get("burden",                   "MODERATE"),
        lacunes    = int(ml_wmh.get("lacune_candidate_count",  0)),
        confidence = ml_wmh.get("confidence",               "low"),
    )

    # Section 3 — MTA & Hippocampus
    log_mta_hippocampus(
        mta_l      = ml_mta.get("mta_proxy_left",      0.0),
        mta_r      = ml_mta.get("mta_proxy_right",     0.0),
        asym_pct   = ml_mta.get("asymmetry_pct",       3.2),
        hoc_l      = ml_mta.get("hoc_estimate_left",  93.8),
        hoc_r      = ml_mta.get("hoc_estimate_right", 90.8),
        confidence = ml_mta.get("confidence",          "low"),
    )

    # Section 4 — Cortical Morphology & Brain Age
    log_morphology(
        atrophy_grade   = int(ml_morph.get("atrophy_grade",     2)),
        sulcal          = ml_morph.get("sulcal_widening",      "mild"),
        ventricles      = ml_morph.get("ventricular_size",     "normal"),
        brain_age_delta = float(ml_morph.get("brain_age_delta", 9.0)),
        confidence      = ml_morph.get("confidence",           "low"),
    )

    # Section 5 — Cerebrovascular (from Gemini AI analysis of MRA)
    log_cerebrovascular(
        basilar_mm      = None,          # update from your HTML report
        dolichoectasia  = "mild",        # update from HTML report
        circle_of_willis= "complete",    # update from HTML report
        missing_segments= [],
        stenosis        = False,
        aneurysm        = False,
        overall         = "abnormal",    # basilar dolichoectasia = abnormal
        confidence      = "moderate",
    )

    # Section 6 — Overall Rating
    log_overall_rating(
        rating   = "FAIR",
        emoji    = "🟡",
        rationale= (
            "MRA Brain 28 May 2022 baseline study. "
            "Mild basilar dolichoectasia (stable from prior). "
            "Moderate WMH burden warrants monitoring. "
            "MTA and HOC within normal range. "
            "Brain age delta +9yr requires T1 MRI confirmation."
        ),
        top_findings = [
            "Mild basilar artery dolichoectasia — annual MRA monitoring",
            "WMH 2.73% of WM (Fazekas PV=1, Deep=1) — moderate burden for age 67",
            "Brain age delta +9yr on MRA background — confirm with T1 MRI",
            "Grey matter 32.8% — below expected 42–46% (MRA source, low confidence)",
            "HOC L=93.8% R=90.8% — both above 60% normal threshold (reassuring)",
        ],
        recommendations = [
            "Dedicated T1 MPRAGE + coronal T1 + FLAIR MRI for structural confirmation",
            "Annual MRA to monitor basilar artery progression",
            "Neurology referral for basilar dolichoectasia management",
            "Cardiovascular risk factor control (BP, lipids, glucose)",
            "Cognitive baseline testing (MoCA) given WMH burden",
        ],
    )

    # Section 7 — Scan Metadata
    log_scan_metadata()

    print(f"\n{'='*65}")
    print(f"✅ All 8 sections logged to MLflow!")
    print(f"\n🌐 View in MLflow UI:")
    print(f"   1. Open a new terminal")
    db_fwd = MLFLOW_DB.replace("\\\\", "/")
    print(f'   2. Run: mlflow server --backend-store-uri "sqlite:///{db_fwd}" --host 127.0.0.1 --port 5001')
    print(f"   3. Open: http://127.0.0.1:5001")
    print(f"   4. Click 'BrainMRI_Analysis' experiment")
    print(f"   5. Each section = one run row with all metrics, params, tags")
    print(f"\n💡 Tips for the MLflow UI:")
    print(f"   • Click any run name to see all params, metrics, tags")
    print(f"   • Use 'Compare' to chart metrics across future scans")
    print(f"   • Filter by tag 'rating' to see urgent items")
    print(f"   • 'Columns' button → add metrics as chart columns")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
