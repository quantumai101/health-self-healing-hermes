import os, sys, json, time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

for _ep in [Path(__file__).parent/".env",
            Path.home()/"Desktop"/"health-self-healing-hermes"/".env"]:
    if _ep.exists():
        load_dotenv(dotenv_path=_ep, override=True)
        break
else:
    load_dotenv(override=True)

try:
    from tqdm import tqdm
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    class Fore:
        RED=GREEN=YELLOW=CYAN=WHITE=""
    class Style:
        RESET_ALL=BRIGHT=""
    def tqdm(x,**k): return x

from google import genai
from google.genai import types
import pydicom, numpy as np, io
from PIL import Image

API_KEY    = os.getenv("GOOGLE_API_KEY","") or os.getenv("GEMINI_API_KEY","")

# ─── PATHS — updated for MRA Brain 28May2022 ──────────────────────────────────
MRA_ROOT   = os.getenv("MRA_LOCAL_PATH", r"I:\MRA Brian 28May2022").strip('"').strip("'")
OUTPUT_DIR = Path(MRA_ROOT)          # reports go to the same folder
OUTPUT_TXT = str(OUTPUT_DIR / "MRA_Analysis_Report.txt")
OUTPUT_HTML= str(OUTPUT_DIR / "MRA_Analysis_Report.html")

MODEL      = "gemini-2.5-flash"

# ─── DICOM root — tries standard sub-paths then falls back to root ─────────────
def _find_dicom_base(root: Path) -> Path:
    """Return the best DICOM directory to walk from."""
    candidates = [
        root / "DICOM" / "PA000001" / "ST000001",
        root / "DICOM",
        root,
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return root   # last resort

DICOM_BASE = _find_dicom_base(Path(MRA_ROOT))

PATIENT = dict(
    name="Zhang Zhi Ming", dob="14/03/1955", age=69, sex="Male",
    scan_date="28 May 2022", facility="MRA Brain 28May2022",
    known_history=(
        "Benign Prostatic Hypertrophy (BPH/Hyperplasia). "
        "Basilar dolichoectasia noted on prior imaging. "
        "Recent CTCA does not confirm hypertension or cardiac disease."
    )
)

# ─── Series routing — MRA-focused (TOF / vessels are highest priority) ─────────
SERIES_ROUTES = {
    # MRA vessel sequences — priority 3
    "TOF_3D":       dict(priority=3, agent="AXIOM", role="vessels"),
    "TOF":          dict(priority=3, agent="AXIOM", role="vessels"),
    "MRA":          dict(priority=3, agent="AXIOM", role="vessels"),
    "ANGIO":        dict(priority=3, agent="AXIOM", role="vessels"),
    "MIP":          dict(priority=3, agent="AXIOM", role="mip"),
    # Structural support sequences
    "T2_FLAIR":     dict(priority=2, agent="AXIOM", role="wmh"),
    "FLAIR":        dict(priority=2, agent="AXIOM", role="wmh"),
    "T1_TIRM":      dict(priority=2, agent="AXIOM", role="t1volume"),
    "TIRM":         dict(priority=2, agent="AXIOM", role="t1volume"),
    "T2_TSE":       dict(priority=1, agent="AXIOM", role="t2struct"),
    "DWI":          dict(priority=2, agent="AXIOM", role="dwi"),
    "DTI":          dict(priority=2, agent="AXIOM", role="dwi"),
    "REPORT":       dict(priority=2, agent="NOVA",  role="pdf_report"),
}

# Keywords whose series also get a SECOND structural-brain pass
# (MRA background tissue carries enough signal for MTA / WMH / GM-WM estimation)
MRA_STRUCTURAL_ALSO = {"TOF_3D", "TOF", "MRA", "ANGIO"}

# ─────────────────────────────────────────────
def setup():
    if not API_KEY:
        print("ERROR: GOOGLE_API_KEY not found in .env"); sys.exit(1)
    print(f"Key: {API_KEY[:8]}...")
    return genai.Client(api_key=API_KEY)

# ─────────────────────────────────────────────
def discover_series():
    """Walk the DICOM tree and return a list of matching series."""
    series_list = []

    def _walk(base: Path):
        """Recursively find leaf directories containing DICOM files."""
        entries = sorted(base.iterdir()) if base.is_dir() else []
        subdirs = [e for e in entries if e.is_dir()]
        if subdirs:
            for sd in subdirs:
                _walk(sd)
            return
        # leaf directory — collect image files
        images = [f for f in sorted(base.iterdir())
                  if f.is_file() and f.suffix.lower() not in
                  {".zip", ".gz", ".tar", ".rar", ".txt", ".xml", ".json", ".html", ".pdf"}]
        if not images:
            return
        mid = images[len(images) // 2]
        try:
            ds   = pydicom.dcmread(str(mid), stop_before_pixels=True)
            desc = getattr(ds, "SeriesDescription", "").strip()
        except Exception:
            return
        if not desc:
            # Fall back to directory name as description
            desc = base.name

        route = None
        matched_kw = None
        for kw, cfg in SERIES_ROUTES.items():
            if kw.upper() in desc.upper():
                route = cfg
                matched_kw = kw
                break

        # If no keyword match, treat as generic structural if it has many slices
        if not route:
            if len(images) >= 5:
                route = dict(priority=1, agent="AXIOM", role="t2struct")
            else:
                return

        series_list.append(dict(
            se_dir=base, se_name=base.name, desc=desc,
            images=images, n_images=len(images), **route
        ))

        # For MRA/TOF series also emit a second structural-brain analysis entry
        # (MTA, hippocampus, GM/WM%, WMH estimation from background tissue)
        if matched_kw in MRA_STRUCTURAL_ALSO:
            series_list.append(dict(
                se_dir=base, se_name=base.name,
                desc=f"{desc} [Structural Brain Analysis]",
                images=images, n_images=len(images),
                priority=2, agent="AXIOM", role="mra_structural"
            ))

    _walk(DICOM_BASE)
    return sorted(series_list, key=lambda x: -x["priority"])

# ─────────────────────────────────────────────
def dicom_to_png(path):
    try:
        ds  = pydicom.dcmread(str(path))
        arr = ds.pixel_array.astype(float)
        if arr.ndim == 3:
            arr = arr[arr.shape[0] // 2]
        lo, hi = arr.min(), arr.max()
        if hi == lo:
            return None
        arr = ((arr - lo) / (hi - lo) * 255).astype(np.uint8)
        img = Image.fromarray(arr).convert("RGB")
        w, h = img.size
        if max(w, h) > 1024:
            s = 1024 / max(w, h)
            img = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        print(f"  DICOM->PNG failed: {e}")
        return None

# ─────────────────────────────────────────────
def get_prompt(role):
    p   = PATIENT
    hdr = (f"Patient: {p['name']}, DOB {p['dob']}, Age {p['age']}, {p['sex']}. "
           f"Scan: {p['scan_date']}, {p['facility']}. History: {p['known_history']}\n\n")

    # ── MRA VESSELS / TOF (PRIMARY for this script) ────────────────────────────
    if role == "vessels":
        return hdr + """Analyse MRA / TOF angiography slices. 
This is a 2022 MRA Brain study. Patient has known basilar dolichoectasia.
Return JSON only — no markdown, no backticks:
{
  "sequence": "MRA_TOF",

  "circle_of_willis": "complete/incomplete",
  "circle_of_willis_missing_segments": ["list any absent segments e.g. AComm, L-PComm, R-PComm"],
  "cow_variant": "normal/fetal PCA/hypoplastic/other",

  "basilar_artery_diameter_mm": "Xmm",
  "basilar_artery_length_mm": "Xmm (if estimable)",
  "basilar_dolichoectasia": "none/mild/moderate/severe",
  "basilar_tortuosity": "none/mild/moderate/severe",
  "basilar_flow_signal": "normal/reduced/absent/turbulent",
  "basilar_cbf_proxy": "normal/mildly reduced/moderately reduced/severely reduced",
  "basilar_compression_risk": "none/low/intermediate/high",

  "vertebral_arteries": {
    "left_va_calibre": "normal/hypoplastic/absent",
    "right_va_calibre": "normal/hypoplastic/absent",
    "va_dominance": "left/right/co-dominant",
    "va_flow_signal": "normal/reduced/absent"
  },

  "ica_bilateral": {
    "left": "normal/stenosis/occlusion",
    "right": "normal/stenosis/occlusion"
  },
  "mca_bilateral": {
    "left": "normal/stenosis/occlusion/hypoplasia",
    "right": "normal/stenosis/occlusion/hypoplasia"
  },
  "aca_bilateral": {
    "left": "normal/stenosis/occlusion/hypoplasia",
    "right": "normal/stenosis/occlusion/hypoplasia"
  },
  "pca_bilateral": {
    "left": "normal/stenosis/occlusion/hypoplasia",
    "right": "normal/stenosis/occlusion/hypoplasia"
  },

  "stenosis_detected": false,
  "stenosis_details": "none / describe location and degree",
  "stenosis_grading": "none/mild(<50%)/moderate(50-69%)/severe(70-99%)/occlusion",

  "aneurysm": false,
  "aneurysm_details": "none / describe location, size, morphology",
  "avm_or_fistula": false,

  "posterior_circulation_overall": "normal/mildly abnormal/moderately abnormal/severely abnormal",
  "anterior_circulation_overall": "normal/mildly abnormal/moderately abnormal/severely abnormal",
  "overall_vasculature": "normal/abnormal",

  "urgent_flag": false,
  "findings_summary": "Detailed narrative summary of MRA findings."
}"""

    # ── MRA STRUCTURAL BRAIN (MTA / Hippocampus / GM-WM% / WMH from MRA bg) ──
    elif role == "mra_structural":
        return hdr + f"""You are analysing the BACKGROUND BRAIN TISSUE visible in MRA / TOF angiography slices.
Although this is an MRA study (not a dedicated structural MRI), the brain parenchyma visible in the
background provides useful information about cortical atrophy, hippocampal volume, white matter
hyperintensities, and grey/white matter distribution.

IMPORTANT: Be explicit about confidence limitations — MRA is not optimised for brain tissue contrast.
Provide best-effort estimates and flag where a dedicated MRI sequence would be needed for confirmation.

Patient age {p['age']}. Return JSON only — no markdown, no backticks:
{{
  "sequence": "MRA_BACKGROUND_STRUCTURAL",
  "assessment_confidence": "low/moderate/high — MRA background tissue only",

  "grey_white_matter": {{
    "grey_matter_pct": "~X% (estimated from visible cortex/sulci)",
    "white_matter_pct": "~X% (estimated from parenchymal signal)",
    "csf_pct": "~X% (estimated from sulci and ventricles)",
    "gm_wm_ratio": "~X:1",
    "gm_status": "NORMAL/MILDLY_REDUCED/MODERATELY_REDUCED — best estimate",
    "confidence_note": "Limited by MRA contrast weighting; recommend T1 MRI for confirmation"
  }},

  "cortical_atrophy": {{
    "cortical_atrophy_grade": "0/1/2/3 — best estimate (0=none, 3=severe)",
    "sulcal_widening": "none/mild/moderate/severe",
    "dominant_region": "frontal/parietal/temporal/generalised/none apparent",
    "ventricular_size": "normal/mildly enlarged/moderately enlarged",
    "confidence_note": "Best estimate from MRA background; dedicated T1 MRI recommended"
  }},

  "mta_hippocampus": {{
    "mta_score_left": "0.0–4.0 or N/A if not visible",
    "mta_score_right": "0.0–4.0 or N/A if not visible",
    "mta_asymmetry_pct": "~X% L vs R or N/A",
    "mta_asymmetry_flag": false,
    "mta_interpretation": "normal for age {p['age']}/borderline/abnormal/not assessable",
    "hippocampal_volume_visual": "preserved/mildly reduced/moderately reduced/severely reduced/not assessable",
    "hoc_estimate_left": "~X% or N/A",
    "hoc_estimate_right": "~X% or N/A",
    "hoc_asymmetry_pct": "~X% or N/A",
    "hoc_asymmetry_flag": false,
    "hoc_interpretation": "normal >60%/borderline/low risk/not assessable",
    "temporal_lobe_appearance": "normal/atrophic/asymmetric",
    "confidence_note": "MTA/HOC best assessed on dedicated coronal T1; this is MRA-background estimate only"
  }},

  "wmh_microvascular": {{
    "wmh_visible_on_mra_bg": "yes/no/uncertain",
    "wmh_periventricular_fazekas": "0/1/2/3 or N/A",
    "wmh_deep_fazekas": "0/1/2/3 or N/A",
    "wmh_burden": "NONE/MILD/MODERATE/SEVERE or NOT_ASSESSABLE",
    "wmh_pct_estimate": "~X% or N/A",
    "lacunes_visible": "none/possible/present — describe",
    "epvs_visible": "none/mild/moderate/severe or N/A",
    "microvascular_significance": "...",
    "confidence_note": "WMH best detected on FLAIR; this is background-signal estimate from MRA"
  }},

  "brain_age_estimate": "~X years or N/A",
  "brain_age_vs_chronological": "younger/same/older than {p['age']} or N/A",
  "age_comparison": "better/average/worse than expected for age {p['age']}",

  "urgent_structural_flag": false,
  "recommended_follow_up_sequences": [
    "e.g. Dedicated T1 MPRAGE for volumetry",
    "T2-FLAIR for WMH quantification",
    "Coronal T1 for MTA scoring"
  ],
  "findings_summary": "Narrative summary of structural brain observations from MRA background tissue, with caveats."
}}"""

    # ── MIP PROJECTIONS ────────────────────────────────────────────────────────
    elif role == "mip":
        return hdr + """Analyse MIP (Maximum Intensity Projection) angiography images.
Return JSON only — no markdown, no backticks:
{
  "sequence": "MIP_PROJECTION",
  "projection_type": "axial/coronal/sagittal/multi-plane",
  "vessel_conspicuity": "excellent/good/fair/poor",
  "posterior_fossa_vessels": "normal/abnormal — describe",
  "supratentorial_vessels": "normal/abnormal — describe",
  "basilar_dolichoectasia_visible": false,
  "basilar_description_from_mip": "...",
  "flow_gaps": "none/describe location",
  "findings_summary": "..."
}"""

    # ── WMH / FLAIR ────────────────────────────────────────────────────────────
    elif role == "wmh":
        return hdr + f"""Analyse T2-FLAIR slices. Return JSON only — no markdown, no backticks:
{{
  "sequence": "T2-FLAIR",
  "wmh_periventricular_fazekas": 0,
  "wmh_deep_fazekas": 0,
  "wmh_burden": "NONE/MILD/MODERATE/SEVERE",
  "wmh_pct_estimate": "~X%",
  "wmh_spatial_distribution": {{
    "frontal_periventricular": "absent/mild/moderate/severe",
    "posterior_periventricular": "absent/mild/moderate/severe",
    "deep_frontal": "absent/mild/moderate/severe",
    "deep_parietal": "absent/mild/moderate/severe",
    "deep_occipital": "absent/mild/moderate/severe",
    "distribution_pattern": "punctate/confluent/mixed",
    "clinical_note": "..."
  }},
  "lacunes": false,
  "lacune_count": "0",
  "enlarged_perivascular_spaces_epvs": "NONE/MILD/MODERATE/SEVERE",
  "epvs_location": "none/basal ganglia/white matter/both",
  "epvs_grade_basal_ganglia": "0/1/2/3/4",
  "epvs_grade_white_matter": "0/1/2/3/4",
  "epvs_glymphatic_implication": "normal/mildly impaired/moderately impaired",
  "epvs_amyloid_clearance_risk": "low/intermediate/high",
  "microvascular_significance": "...",
  "age_comparison": "better/average/worse than expected for age {p['age']}",
  "urgent_flag": false,
  "findings_summary": "..."
}}"""

    # ── T1 VOLUME / TIRM ───────────────────────────────────────────────────────
    elif role == "t1volume":
        return hdr + f"""Analyse T1/TIRM slices. Return JSON only — no markdown, no backticks:
{{
  "sequence": "T1_TIRM",
  "grey_matter_pct": "~X%",
  "white_matter_pct": "~X%",
  "csf_pct": "~X%",
  "gm_status": "NORMAL/MILDLY_REDUCED/MODERATELY_REDUCED",
  "cortical_atrophy_grade": 0,
  "sulcal_morphology": {{
    "frontal_sulcal_width": "normal/mildly widened/moderately widened",
    "parietal_sulcal_width": "normal/mildly widened/moderately widened",
    "temporal_sulcal_width": "normal/mildly widened/moderately widened",
    "dominant_region": "...",
    "clinical_note": "..."
  }},
  "mta_score_left": 0.0,
  "mta_score_right": 0.0,
  "mta_asymmetry_pct": "~X% difference L vs R",
  "mta_interpretation": "normal for age/borderline/abnormal",
  "mta_asymmetry_flag": false,
  "hippocampal_occupancy_hoc": "~X%",
  "hoc_left_pct": "~X%",
  "hoc_right_pct": "~X%",
  "hoc_asymmetry_pct": "~X% difference L vs R",
  "hoc_interpretation": "normal >60%/borderline/low risk",
  "hoc_asymmetry_flag": false,
  "regional_atrophy": {{
    "frontal": "none/mild/moderate/severe",
    "temporal": "none/mild/moderate/severe",
    "parietal": "none/mild/moderate/severe",
    "occipital": "none/mild/moderate/severe",
    "hippocampal": "none/mild/moderate/severe",
    "entorhinal": "none/mild/moderate/severe"
  }},
  "ventricular_size": "normal/enlarged",
  "brain_age_estimate": "~X years",
  "brain_age_vs_chronological": "younger/same/older than {p['age']}",
  "findings_summary": "..."
}}"""

    # ── T2 STRUCTURAL ──────────────────────────────────────────────────────────
    elif role == "t2struct":
        return hdr + """Analyse T2 slices. Return JSON only — no markdown, no backticks:
{
  "sequence": "T2_TSE",
  "basal_ganglia": "normal",
  "cerebellum": "normal",
  "focal_lesions": false,
  "overall_structure": "normal",
  "findings_summary": "..."
}"""

    # ── DWI / DTI ──────────────────────────────────────────────────────────────
    elif role == "dwi":
        return hdr + """Analyse DWI or DTI slices. Return JSON only — no markdown, no backticks:
{
  "sequence": "DWI_DTI",
  "acute_infarction": false,
  "restricted_diffusion_regions": "none/specify locations",
  "adc_map_impression": "normal/low ADC regions present",
  "white_matter_tract_integrity": {
    "corpus_callosum": "normal/mildly impaired/moderately impaired/severely impaired",
    "corticospinal_tract": "normal/mildly impaired/moderately impaired/severely impaired",
    "superior_longitudinal_fasciculus": "normal/mildly impaired/moderately impaired/severely impaired",
    "cingulum": "normal/mildly impaired/moderately impaired/severely impaired",
    "overall_fa_impression": "normal/mildly reduced/moderately reduced"
  },
  "findings_summary": "..."
}"""

    # ── PDF REPORT ─────────────────────────────────────────────────────────────
    elif role == "pdf_report":
        return hdr + """Analyse report text. Return JSON only — no markdown, no backticks:
{
  "report_type": "radiology",
  "key_findings": [],
  "diagnoses": [],
  "recommendations": [],
  "urgent_flag": false,
  "findings_summary": "..."
}"""

    else:
        return hdr + """Return JSON only — no markdown, no backticks:
{"sequence":"unknown","findings_summary":"..."}"""

# ─────────────────────────────────────────────
def analyse(client, series):
    role   = series["role"]
    prompt = get_prompt(role)
    images = series["images"]
    slices = images[len(images)//4 : len(images)*3//4]
    picks  = slices[::max(1, len(slices)//3)][:3]

    parts     = [types.Part.from_text(text=prompt)]
    png_count = 0
    for sl in picks:
        png = dicom_to_png(sl)
        if png:
            parts.append(types.Part.from_bytes(data=png, mime_type="image/png"))
            png_count += 1

    if len(parts) == 1:
        return {"error": "no slices", "series": series["desc"], "slices_analysed": 0}

    result = {"error": "unknown", "slices_analysed": 0}
    for attempt in range(3):
        try:
            resp = client.models.generate_content(model=MODEL, contents=parts)
            raw  = resp.text.strip()
            if "```" in raw:
                raw = "\n".join(l for l in raw.split("\n") if not l.strip().startswith("```"))
            result = json.loads(raw.strip())
            result["slices_analysed"] = png_count
            break
        except json.JSONDecodeError:
            result = {"raw_analysis": resp.text, "parse_error": True, "slices_analysed": png_count}
            break
        except Exception as e:
            err_str = str(e)
            if "429" in err_str:
                print(f"  ⏳ Rate limited — waiting 90s..."); time.sleep(90)
            elif "11001" in err_str or "getaddrinfo" in err_str or "ConnectionError" in err_str.lower():
                wait = 20 * (attempt + 1)
                print(f"  🌐 Network error (attempt {attempt+1}/3) — retrying in {wait}s...")
                time.sleep(wait)
                if attempt == 2:
                    result = {"error": err_str, "slices_analysed": 0}
            elif attempt == 2:
                result = {"error": err_str, "slices_analysed": 0}
            else:
                time.sleep(8)

    result.update(
        series_name=series["se_name"], series_desc=series["desc"],
        total_images_in_series=series["n_images"],
        agent=series["agent"], role=role
    )
    return result

# ─────────────────────────────────────────────
def sentinel_summary(client, results):
    try:
        findings = json.dumps(results, indent=2)[:30000]
        prompt = f"""You are SENTINEL. Compile MASTER MRA BRAIN REPORT v3 — MRA Focus.
Patient: {PATIENT["name"]} | Age: {PATIENT["age"]} | {PATIENT["scan_date"]}
History: {PATIENT["known_history"]}

RATING SYSTEM — use EXACTLY these four emoji in every Rating column cell and flag list:
  🟢 GREEN  = Normal / within expected range for age
  🟡 YELLOW = Mild deviation / monitor — not urgent
  🟠 ORANGE = Moderate / warrants clinical attention soon
  🔴 RED    = Severe / urgent — requires specialist review

Every table MUST include a "Rating" column and a "Notes" column.
Use 🟢🟡🟠🔴 consistently — never use other symbols for ratings.

Include ALL sections below in order:

1. OVERALL RATING — one word (EXCELLENT/GOOD/FAIR/CONCERNING/CRITICAL) + emoji + one-paragraph rationale

2. CEREBROVASCULAR OVERVIEW — table: Vessel/Parameter | Finding | Normal | Rating | Notes
   Include ALL major vessels: Basilar, Left VA, Right VA, Left ICA, Right ICA,
   Left MCA, Right MCA, Left ACA, Right ACA, Left PCA, Right PCA

3. BASILAR ARTERY DETAIL — table: Parameter | Finding | Normal | Rating | Notes
   Include: Diameter mm, Length mm, Dolichoectasia severity, Tortuosity, Flow signal,
   CBF proxy, Compression risk, vs prior imaging (2022 is baseline)

4. CIRCLE OF WILLIS — table: Parameter | Finding | Normal | Rating | Notes
   Include: Completeness, Missing segments, CoW variant (fetal PCA / hypoplastic etc)

5. POSTERIOR CIRCULATION — table: Vessel | Finding | Normal | Rating | Notes
   Include: Basilar, Bilateral VA, PCA bilateral, PICA, AICA (if visible)

6. ANTERIOR CIRCULATION — table: Vessel | Finding | Normal | Rating | Notes
   Include: ICA bilateral, MCA bilateral, ACA bilateral

7. STENOSIS ASSESSMENT — table: Location | Degree | Grading | Rating | Notes
   If none detected, state clearly with 🟢

8. ANEURYSM / AVM SCREEN — table: Location | Size | Morphology | Rating | Notes
   If none detected, state clearly with 🟢

9. GREY MATTER & WHITE MATTER % — table: Parameter | Finding | Normal (Age {PATIENT["age"]}yo Male) | Rating | Notes
   Draw from mra_structural results (grey_white_matter block). Include:
   Grey Matter %, White Matter %, CSF %, GM/WM Ratio, GM Status, Brain Age Estimate, Brain Age vs Chronological.
   If only MRA background available, note confidence limitations clearly in Notes column.
   Normal ranges: GM ~42-46%, WM ~40-46%, CSF ~10-16%, GM/WM ratio ~1.0:1.

10. MTA SCORE & HIPPOCAMPUS — table: Parameter | Left (L) | Right (R) | Asymmetry (L vs R) | Normal for Age {PATIENT["age"]}yo | Rating | Notes
    Draw from mra_structural mta_hippocampus block. Include:
    MTA Score, Hippocampal Occupancy (HOC%), HOC Asymmetry Index, Temporal Lobe Appearance.
    Flag if MTA > 1.5 or HOC < 60% or asymmetry > 10%. Normal: MTA 0-1, HOC >60%, asymmetry <10%.
    If not assessable from MRA background, mark N/A with 🟡 and recommend dedicated coronal T1.

11. MICROVASCULAR DISEASE — table: Parameter | Finding | Normal | Rating | Notes
    Draw from mra_structural wmh_microvascular block. Include:
    Fazekas Grade (Periventricular), Fazekas Grade (Deep WM), WMH % Burden, Lacunes, EPVS.
    Normal: Fazekas 0-1, WMH <1-2%, no lacunes. If not assessable, mark N/A with 🟡 and recommend FLAIR.

12. CORTICAL ATROPHY — table: Parameter | Finding | Normal | Rating | Notes
    Draw from mra_structural cortical_atrophy block. Include:
    Cortical Atrophy Grade, Sulcal Widening, Dominant Region, Ventricular Size.
    Normal: Grade 0-1, no sulcal widening, normal ventricles.

13. WMH / MICROVASCULAR (from dedicated FLAIR if available) — table: Parameter | Finding | Normal | Rating | Notes
    If FLAIR series present use those results; if not, note clearly and cross-reference section 11.

14. BRAIN VOLUME / ATROPHY (from dedicated T1 if available) — table: Parameter | Finding | Normal | Rating | Notes
    If T1 series present use those results; if not, note clearly and cross-reference sections 9-12.

15. RED FLAGS 🔴 — bullet list, urgent items only
16. ORANGE FLAGS 🟠 — bullet list, moderate items needing attention
17. YELLOW FLAGS 🟡 — bullet list, mild monitoring items
18. GREEN FLAGS 🟢 — bullet list, normal/positive findings
19. TOP 5 RECOMMENDED ACTIONS — numbered, most urgent first
    Always include: "Obtain dedicated T1 MPRAGE + coronal T1 + FLAIR MRI for definitive structural assessment"
    if only MRA-background structural estimates are available.
20. BASELINE NOTE — paragraph noting this is the 28 May 2022 MRA establishing baseline
    for future comparison (esp. basilar dolichoectasia progression monitoring)

DISCLAIMER at end.

ALL FINDINGS: {findings}"""
        resp = client.models.generate_content(model=MODEL, contents=prompt)
        return resp.text
    except Exception as e:
        return f"[SENTINEL failed: {e}]"

# ─────────────────────────────────────────────
def write_txt(results, sentinel, path, stats):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("="*70+"\n")
        f.write(f"  MRA BRAIN ANALYSIS — {PATIENT['name']} | Age {PATIENT['age']}\n")
        f.write(f"  Scan Date: {PATIENT['scan_date']} | {PATIENT['facility']}\n")
        f.write(f"  History: {PATIENT['known_history']}\n")
        f.write(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  Series: {stats['series_ok']}/{stats['series_total']} | "
                f"Total images: {stats['total_images']} | Slices to AI: {stats['slices_sent']}\n")
        f.write("="*70+"\n\n"+sentinel+"\n\n")
        for i, r in enumerate(results, 1):
            f.write(f"{'─'*60}\n{i}. {r.get('series_desc','?')} | "
                    f"{r.get('total_images_in_series','?')} imgs | "
                    f"{r.get('slices_analysed','?')} slices sent\n{'─'*60}\n")
            clean = {k: v for k, v in r.items()
                     if k not in ("series_name","series_desc","agent","role",
                                  "total_images_in_series","slices_analysed")}
            f.write(json.dumps(clean, indent=2)+"\n\n")
        f.write("="*70+"\n⚕️ AI only — review with neurologist / neuroradiologist.\n"+"="*70+"\n")

# ─────────────────────────────────────────────
def write_html(results, sentinel, path, stats):
    import html as hl, re
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    def apply_emoji_badges(text):
        text = text.replace("🔴", "<span class='badge-red'>🔴 Urgent</span>")
        text = text.replace("🟠", "<span class='badge-orange'>🟠 Warning</span>")
        text = text.replace("🟡", "<span class='badge-yellow'>🟡 Mild</span>")
        text = text.replace("🟢", "<span class='badge-green'>🟢 Normal</span>")
        return text

    def md2h(t):
        o = []
        in_table = False
        in_list  = False

        for raw_line in t.split("\n"):
            l = raw_line

            if l.startswith("### "):
                if in_list:  o.append("</ul>"); in_list = False
                if in_table: o.append("</table>"); in_table = False
                o.append(f'<h3>{hl.escape(l[4:])}</h3>'); continue
            if l.startswith("## "):
                if in_list:  o.append("</ul>"); in_list = False
                if in_table: o.append("</table>"); in_table = False
                o.append(f'<h2>{hl.escape(l[3:])}</h2>'); continue
            if l.startswith("# "):
                if in_list:  o.append("</ul>"); in_list = False
                if in_table: o.append("</table>"); in_table = False
                o.append(f'<h1>{hl.escape(l[2:])}</h1>'); continue

            if l.startswith("|"):
                cells = [c.strip() for c in l.split("|")[1:-1]]
                if all(set(c) <= set("-: ") for c in cells):
                    continue
                if not in_table:
                    o.append("<table>"); in_table = True; is_first_row = True
                else:
                    is_first_row = False
                tag = "th" if is_first_row else "td"
                colored = []
                for c in cells:
                    cu = c.upper()
                    if tag == "td":
                        if "🔴" in c:   cell_class = " class='val-red'"
                        elif "🟠" in c: cell_class = " class='val-orange'"
                        elif "🟡" in c: cell_class = " class='val-yellow'"
                        elif "🟢" in c: cell_class = " class='val-green'"
                        elif any(x in cu for x in ["SEVERE","CRITICAL","URGENT","HIGH"]):
                            cell_class = " class='val-red'"
                        elif any(x in cu for x in ["MODERATE","WARNING","INTERMEDIATE"]):
                            cell_class = " class='val-orange'"
                        elif any(x in cu for x in ["MILD","BORDERLINE","INCOMPLETE","REDUCED"]):
                            cell_class = " class='val-yellow'"
                        elif any(x in cu for x in ["NORMAL","NONE","COMPLETE","ABSENT","LOW"]):
                            cell_class = " class='val-green'"
                        else:
                            cell_class = ""
                        colored.append(f"<{tag}{cell_class}>{apply_emoji_badges(hl.escape(c))}</{tag}>")
                    else:
                        colored.append(f"<{tag}>{hl.escape(c)}</{tag}>")
                o.append("<tr>"+"".join(colored)+"</tr>")
                continue
            else:
                if in_table: o.append("</table>"); in_table = False

            if l.startswith(("- ","* ","  - ","  * ")):
                txt = l.lstrip("- *").lstrip()
                txt = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", txt)
                txt = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         txt)
                txt = apply_emoji_badges(hl.escape(txt))
                if not in_list: o.append("<ul>"); in_list = True
                o.append(f"<li>{txt}</li>")
                continue
            else:
                if in_list: o.append("</ul>"); in_list = False

            if l.strip() in ("---", "***", "___"):
                o.append("<hr>"); continue

            if l.strip():
                l2 = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", l)
                l2 = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         l2)
                l2 = apply_emoji_badges(hl.escape(l2))
                o.append(f"<p>{l2}</p>")

        if in_list:  o.append("</ul>")
        if in_table: o.append("</table>")
        return "\n".join(o)

    sh = md2h(sentinel)

    ROLE_LABELS = {
        "vessels":      "🩸 MRA Cerebrovascular",
        "mra_structural":"🧠 MRA Structural Brain (GM/WM/MTA/WMH)",
        "mip":          "🔭 MIP Projection",
        "wmh":       "🧠 WMH / Glymphatic",
        "t1volume":  "📐 Volume / Atrophy",
        "dwi":       "🔬 Diffusion / Tracts",
        "t2struct":  "🔍 T2 Structure",
        "pdf_report":"📄 Report PDF",
    }

    def val_color(k, v):
        sv = str(v).upper()
        if any(x in sv for x in ["SEVERE","CRITICAL","TRUE","HIGH RISK","OCCLUSION"]):
            return "style='color:#f85149;font-weight:bold'"
        if any(x in sv for x in ["MODERATE","MILD","AMBER","BORDERLINE","INTERMEDIATE","REDUCED","INCOMPLETE"]):
            return "style='color:#d29922;font-weight:bold'"
        if any(x in sv for x in ["NORMAL","NONE","FALSE","COMPLETE","YOUNGER","ABSENT","LOW"]):
            return "style='color:#3fb950'"
        return ""

    def render_value(v):
        if isinstance(v, dict):
            rows = "".join(
                f"<tr><td class='sub-key'>{hl.escape(str(sk))}</td>"
                f"<td {val_color(sk,sv)}>{hl.escape(str(sv))}</td></tr>"
                for sk, sv in v.items()
            )
            return f"<table class='sub-table'>{rows}</table>"
        if isinstance(v, list):
            return "<ul class='inline-list'>"+"".join(f"<li>{hl.escape(str(i))}</li>" for i in v)+"</ul>"
        return f"<span {val_color('',v)}>{hl.escape(str(v))}</span>"

    SKIP = {"series_name","series_desc","agent","role"}
    HIGHLIGHT_KEYS = {
        # Vessel findings
        "basilar_artery_diameter_mm","basilar_artery_length_mm","basilar_dolichoectasia",
        "basilar_tortuosity","basilar_cbf_proxy","basilar_compression_risk",
        "circle_of_willis","circle_of_willis_missing_segments","cow_variant",
        "stenosis_detected","stenosis_details","stenosis_grading",
        "aneurysm","aneurysm_details","avm_or_fistula",
        "mca_bilateral","aca_bilateral","pca_bilateral","ica_bilateral","vertebral_arteries",
        "posterior_circulation_overall","anterior_circulation_overall","overall_vasculature",
        # Structural brain from MRA background
        "grey_white_matter","cortical_atrophy","mta_hippocampus","wmh_microvascular",
        "grey_matter_pct","white_matter_pct","csf_pct","gm_wm_ratio","gm_status",
        "mta_score_left","mta_score_right","mta_asymmetry_pct","mta_asymmetry_flag",
        "hoc_estimate_left","hoc_estimate_right","hoc_asymmetry_pct","hoc_asymmetry_flag",
        "hoc_interpretation","hippocampal_volume_visual","temporal_lobe_appearance",
        "wmh_pct_estimate","wmh_burden","wmh_periventricular_fazekas","wmh_deep_fazekas",
        "lacunes_visible","epvs_visible",
        "brain_age_estimate","brain_age_vs_chronological",
        "cortical_atrophy_grade","sulcal_widening","ventricular_size",
    }

    NORMAL_RANGES = {
        # MRA vessel
        "basilar_artery_diameter_mm":  "3.0–4.5 mm",
        "basilar_dolichoectasia":      "none",
        "basilar_tortuosity":          "none",
        "basilar_flow_signal":         "normal",
        "basilar_cbf_proxy":           "normal",
        "basilar_compression_risk":    "none",
        "circle_of_willis":            "complete",
        "stenosis_detected":           "False",
        "aneurysm":                    "False",
        "avm_or_fistula":              "False",
        "mca_bilateral":               "normal bilateral",
        "aca_bilateral":               "normal bilateral",
        "pca_bilateral":               "normal bilateral",
        "ica_bilateral":               "normal bilateral",
        # WMH
        "wmh_burden":                  "NONE or MILD",
        "wmh_periventricular_fazekas": "0–1 (age-related)",
        "wmh_deep_fazekas":            "0",
        "lacunes":                     "False",
        "lacunes_visible":             "none",
        "epvs_visible":                "none to mild",
        # Volume / GM-WM
        "grey_matter_pct":             "~42–46%",
        "white_matter_pct":            "~40–46%",
        "csf_pct":                     "~10–16%",
        "gm_wm_ratio":                 "~1.0:1",
        "gm_status":                   "NORMAL",
        "cortical_atrophy_grade":      "0–1",
        "sulcal_widening":             "none to mild",
        "ventricular_size":            "normal",
        # MTA / Hippocampus
        "mta_score_left":              "≤ 1.5 (normal for age 69)",
        "mta_score_right":             "≤ 1.5 (normal for age 69)",
        "mta_asymmetry_pct":           "< 10% L vs R",
        "hoc_estimate_left":           "> 60%",
        "hoc_estimate_right":          "> 60%",
        "hoc_asymmetry_pct":           "< 10% L vs R",
        "hippocampal_volume_visual":   "preserved",
        "brain_age_estimate":          "≈ 69 years",
        "brain_age_vs_chronological":  "same or younger",
        # DWI
        "acute_infarction":            "False",
    }

    cards = ""
    for r in results:
        if r.get("role") == "pdf_report":
            continue
        ok    = "error" not in r or "raw_analysis" in r
        badge = f'<span class="badge {"ok" if ok else "err"}">{"✓" if ok else "✗"}</span>'
        role  = r.get("role","")
        label = ROLE_LABELS.get(role, role)

        if not ok and "raw_analysis" not in r:
            err_msg = r.get("error","unknown error")
            cards += f"""
<div class='card card-error'>
  <div class='card-header'>
    {badge}
    <span class='role-label'>{label}</span>
    <strong>{hl.escape(r.get('series_desc','?'))}</strong>
    <span class='meta'>{r.get('series_name','?')} | {r.get('total_images_in_series','?')} imgs</span>
  </div>
  <div class='error-body'>⚠️ Series could not be analysed: <code>{hl.escape(err_msg)}</code><br>
  <em>Re-run the script — retry logic will attempt recovery.</em></div>
</div>"""
            continue

        rows = ""
        for k, v in r.items():
            if k in SKIP: continue
            is_highlight = k in HIGHLIGHT_KEYS
            row_class    = " class='highlight-row'" if is_highlight else ""
            ref          = NORMAL_RANGES.get(k, "")
            ref_cell     = (f"<td class='ref-col'>{hl.escape(ref)}</td>"
                            if ref else "<td class='ref-col ref-na'>—</td>")
            rows += (f"<tr{row_class}>"
                     f"<td class='key-col'>{hl.escape(k)}</td>"
                     f"<td>{render_value(v)}</td>"
                     f"{ref_cell}</tr>")

        cards += f"""
<div class='card'>
  <div class='card-header'>
    {badge}
    <span class='role-label'>{label}</span>
    <strong>{hl.escape(r.get('series_desc','?'))}</strong>
    <span class='meta'>{r.get('series_name','?')} | {r.get('total_images_in_series','?')} imgs
      | {r.get('slices_analysed','?')} slices | Agent: {r.get('agent','?')}</span>
  </div>
  <table>
    <tr>
      <th class='key-col'>Metric</th>
      <th>Patient Finding</th>
      <th class='ref-col'>Normal Range (Age {PATIENT['age']} Male)</th>
    </tr>
    {rows}
  </table>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>MRA Brain 28May2022 — {PATIENT["name"]}</title>
<style>
:root{{
  --bg:#0d1117; --s:#161b22; --b:#30363d; --t:#e6edf3; --m:#8b949e;
  --a:#58a6ff;  --g:#3fb950; --y:#d29922; --r:#f85149;
  --highlight-bg:#1c2333;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--t);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.6;padding:2rem}}
.hdr{{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);border-radius:12px;padding:2rem;margin-bottom:2rem}}
.hdr h1{{font-size:1.8rem;color:#fff;margin-bottom:.5rem}}
.hdr .m{{color:#a8c8f8;font-size:.9rem}}
.version-badge{{display:inline-block;background:#1b4f72;color:#aed6f1;font-size:.75rem;padding:.15rem .5rem;border-radius:4px;margin-left:.5rem;vertical-align:middle}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}}
.stat{{background:var(--s);border:1px solid var(--b);border-radius:8px;padding:1rem;text-align:center}}
.stat .v{{font-size:2rem;font-weight:700;color:var(--a)}}
.stat .l{{font-size:.8rem;color:var(--m)}}
.sec{{background:var(--s);border:1px solid var(--b);border-radius:12px;padding:1.5rem;margin-bottom:1.5rem}}
h1{{color:var(--a);font-size:1.5rem;margin:1rem 0 .5rem}}
h2{{color:var(--a);font-size:1.2rem;margin:1rem 0 .5rem;border-bottom:1px solid var(--b);padding-bottom:.5rem}}
h3{{color:#79c0ff;font-size:1rem;margin:.8rem 0 .3rem}}
p{{margin:.5rem 0}} li{{margin:.25rem 0 .25rem 1.5rem}}
strong{{color:#f0f6fc}} em{{color:var(--m)}} hr{{border:none;border-top:1px solid var(--b);margin:1rem 0}}
table{{width:100%;border-collapse:collapse;margin:.5rem 0;font-size:.9rem}}
th{{background:#21262d;color:var(--a);padding:.5rem;text-align:left}}
td{{padding:.4rem .5rem;border-bottom:1px solid var(--b);vertical-align:top;word-break:break-word}}
tr:hover td{{background:#21262d}}
.val-red{{color:var(--r);font-weight:600}} .val-orange{{color:#f0883e;font-weight:600}}
.val-yellow{{color:var(--y);font-weight:600}} .val-green{{color:var(--g)}}
.badge-red{{display:inline-block;background:#3d0e0e;color:#f85149;border:1px solid #f8514955;border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700;white-space:nowrap}}
.badge-orange{{display:inline-block;background:#2d1a08;color:#f0883e;border:1px solid #f0883e55;border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700;white-space:nowrap}}
.badge-yellow{{display:inline-block;background:#2d2008;color:#d29922;border:1px solid #d2992255;border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700;white-space:nowrap}}
.badge-green{{display:inline-block;background:#0d2818;color:#3fb950;border:1px solid #3fb95055;border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700;white-space:nowrap}}
.card{{background:#0d1117;border:1px solid var(--b);border-radius:10px;margin-bottom:1rem;overflow:hidden}}
.card-header{{background:var(--s);padding:.75rem 1rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}}
.badge{{padding:.2rem .5rem;border-radius:4px;font-size:.8rem;font-weight:700}}
.badge.ok{{background:#1a472a;color:var(--g)}} .badge.err{{background:#4a1a1a;color:var(--r)}}
.role-label{{font-size:.8rem;background:#21262d;color:#79c0ff;padding:.15rem .4rem;border-radius:4px}}
.meta{{color:var(--m);font-size:.8rem;margin-left:auto}}
.card table td.key-col{{color:var(--m);width:28%;font-size:.82rem;font-family:monospace}}
.card table th.key-col{{color:#79c0ff;font-size:.82rem;width:28%}}
.card table td.ref-col{{color:#6e7681;font-size:.8rem;width:28%;font-style:italic;border-left:1px solid var(--b);padding-left:.6rem}}
.card table th.ref-col{{color:#79c0ff;font-size:.82rem;border-left:1px solid var(--b);padding-left:.6rem}}
.ref-na{{opacity:.3}}
.highlight-row td{{background:var(--highlight-bg)!important;border-left:3px solid var(--a)}}
.highlight-row td.key-col{{color:#79c0ff}}
.card-error .error-body{{padding:.75rem 1rem;font-size:.88rem;color:var(--y)}}
.card-error .error-body code{{background:#21262d;padding:.1rem .3rem;border-radius:3px;color:var(--r);font-size:.82rem}}
.sub-table{{background:#0d1117;margin:0;border:none;font-size:.82rem}}
.sub-table td{{border-bottom:1px solid #21262d;padding:.25rem .4rem}}
.sub-table .sub-key{{color:var(--m);width:45%;font-style:italic}}
.inline-list{{margin:.25rem 0 .25rem 1rem;font-size:.85rem}}
.baseline-note{{background:#0d2137;border:1px solid #1f4a7a;border-radius:8px;padding:.75rem 1rem;margin-bottom:1.5rem;font-size:.85rem;color:#90caf9}}
.baseline-note strong{{color:#58a6ff}}
.disc{{background:#1a0a0a;border:1px solid #f8514933;border-radius:8px;padding:1rem;color:var(--r);font-size:.85rem;margin-top:2rem}}
</style>
</head>
<body>

<div class="hdr">
  <h1>🩸 MRA Brain Analysis Report <span class="version-badge">28 May 2022 — Baseline</span></h1>
  <div class="m">
    <strong>{PATIENT["name"]}</strong> | DOB: {PATIENT["dob"]} | Age: {PATIENT["age"]} | {PATIENT["sex"]}<br>
    Scan: {PATIENT["scan_date"]} | {PATIENT["facility"]}<br>
    History: {PATIENT["known_history"]}<br>
    Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | AI: Google {MODEL}
  </div>
</div>

<div class="baseline-note">
  <strong>📌 Baseline Study Note:</strong>
  This MRA Brain (28 May 2022) serves as the <strong>baseline reference</strong> for cerebrovascular assessment,
  particularly for basilar artery dolichoectasia progression monitoring.
  All future MRA/MRI studies should be compared against these findings.
  Output files saved to: <code>I:&#92;MRA Brian 28May2022&#92;</code>
</div>

<div class="stats">
  <div class="stat"><div class="v">{stats["series_ok"]}/{stats["series_total"]}</div><div class="l">Series Analysed</div></div>
  <div class="stat"><div class="v">{stats["total_images"]}</div><div class="l">Total DICOM Images</div></div>
  <div class="stat"><div class="v">{stats["slices_sent"]}</div><div class="l">Slices Sent to AI</div></div>
  <div class="stat"><div class="v">{stats["series_total"]}</div><div class="l">Series Found</div></div>
</div>

<div class="sec"><h2>🛡️ SENTINEL Master MRA Report</h2>{sh}</div>
<div class="sec"><h2>🔬 Detailed Per-Series Findings</h2>{cards}</div>

<div class="disc">
  ⚕️ <strong>CLINICAL DISCLAIMER:</strong> AI-generated analysis only.
  All findings must be reviewed and validated by a qualified neuroradiologist or neurologist
  before any clinical decision is made. This report does not constitute a medical diagnosis.
</div>

</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

# ─────────────────────────────────────────────
def main():
    print(f"\n{'='*60}\n  🩸 MRA BRAIN ANALYSIS — {PATIENT['scan_date']}\n"
          f"  {PATIENT['name']} | Age {PATIENT['age']}\n"
          f"  Source:  {MRA_ROOT}\n"
          f"  Reports: {OUTPUT_DIR}\n{'='*60}\n")

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    client = setup()
    print("\n📂 Scanning DICOM series...")
    series_list = discover_series()
    if not series_list:
        print(f"No series found under: {DICOM_BASE}")
        print("Check that I:\\MRA Brian 28May2022 contains DICOM files.")
        sys.exit(0)

    print(f"\n✓ {len(series_list)} series found:")
    for s in series_list:
        print(f"  {s['se_name']} | {s['desc']} | {s['n_images']} imgs → role:{s['role']}")
    print()

    results      = []
    total_images = sum(s["n_images"] for s in series_list)
    slices_sent  = 0

    for s in series_list:
        print(f"🔬 {s['se_name']} — {s['desc']} ({s['n_images']} images)...")
        r = analyse(client, s)
        results.append(r)
        slices_sent += r.get("slices_analysed", 0)
        ok = "error" not in r or "raw_analysis" in r
        print(f"  {'✓' if ok else '✗'} Done — {r.get('slices_analysed',0)} slices sent")
        time.sleep(8)

    stats = dict(
        series_ok    = sum(1 for r in results if "error" not in r or "raw_analysis" in r),
        series_total = len(results),
        total_images = total_images,
        slices_sent  = slices_sent,
    )

    print("\n🛡️  SENTINEL compiling master report...")
    master = sentinel_summary(client, results)

    write_txt(results, master, OUTPUT_TXT, stats)
    write_html(results, master, OUTPUT_HTML, stats)

    print(master[:2000])
    print(f"\n✅ Reports saved to:\n"
          f"   TXT  → {OUTPUT_TXT}\n"
          f"   HTML → {OUTPUT_HTML}\n"
          f"   Stats: {stats}\n")

if __name__ == "__main__":
    main()
