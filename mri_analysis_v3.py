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
MRI_ROOT   = os.getenv("MRI_LOCAL_PATH", r"C:\MRI Brain 5Jan2024").strip(chr(34)).strip("'")
REPORTS_IN = os.getenv("MEDICAL_REPORTS_PATH", r"C:\Medical Reports 17Feb2026").strip(chr(34)).strip("'")
OUTPUT_TXT = str(Path(REPORTS_IN)/"MRI_Analysis_Report.txt")
OUTPUT_HTML= str(Path(REPORTS_IN)/"MRI_Analysis_Report.html")
MODEL      = "gemini-2.5-flash"
DICOM_BASE = Path(MRI_ROOT)/"DICOM"/"PA000001"/"ST000001"

PATIENT = dict(
    name="Zhang Zhi Ming", dob="14/03/1955", age=69, sex="Male",
    scan_date="05 January 2024", facility="Castlereagh Imaging",
    known_history="Benign Prostatic Hypertrophy (BPH/Hyperplasia). Recent CTCA does not confirm hypertension or cardiac disease."
)

SERIES_ROUTES = {
    "T2_FLAIR": dict(priority=3, agent="AXIOM", role="wmh"),
    "FLAIR":    dict(priority=3, agent="AXIOM", role="wmh"),
    "T1_TIRM":  dict(priority=2, agent="AXIOM", role="t1volume"),
    "TIRM":     dict(priority=2, agent="AXIOM", role="t1volume"),
    "T2_TSE":   dict(priority=1, agent="AXIOM", role="t2struct"),
    "TOF_3D":   dict(priority=1, agent="AXIOM", role="vessels"),
    "DWI":      dict(priority=2, agent="AXIOM", role="dwi"),
    "DTI":      dict(priority=2, agent="AXIOM", role="dwi"),
    "REPORT":   dict(priority=3, agent="NOVA",  role="pdf_report"),
}

# ─────────────────────────────────────────────
def setup():
    if not API_KEY:
        print("ERROR: GOOGLE_API_KEY not found in .env"); sys.exit(1)
    print(f"Key: {API_KEY[:8]}...")
    return genai.Client(api_key=API_KEY)

# ─────────────────────────────────────────────
def discover_series():
    series_list = []
    for se_dir in sorted(DICOM_BASE.iterdir()):
        if not se_dir.is_dir(): continue
        images = [f for f in sorted(se_dir.iterdir())
                  if f.is_file() and f.suffix.lower() not in {".zip",".gz",".tar",".rar",".txt",".xml",".json"}]
        if not images: continue
        mid = images[len(images)//2]
        try:
            ds   = pydicom.dcmread(str(mid), stop_before_pixels=True)
            desc = getattr(ds, "SeriesDescription", "").strip()
        except: continue
        if not desc: continue
        route = None
        for kw, cfg in SERIES_ROUTES.items():
            if kw.upper() in desc.upper(): route = cfg; break
        if not route: continue
        series_list.append(dict(se_dir=se_dir, se_name=se_dir.name, desc=desc,
                                images=images, n_images=len(images), **route))
    return sorted(series_list, key=lambda x: -x["priority"])

# ─────────────────────────────────────────────
def dicom_to_png(path):
    try:
        ds  = pydicom.dcmread(str(path))
        arr = ds.pixel_array.astype(float)
        if arr.ndim == 3: arr = arr[arr.shape[0]//2]
        lo, hi = arr.min(), arr.max()
        if hi == lo: return None
        arr = ((arr-lo)/(hi-lo)*255).astype(np.uint8)
        img = Image.fromarray(arr).convert("RGB")
        w, h = img.size
        if max(w,h) > 1024:
            s = 1024/max(w,h)
            img = img.resize((int(w*s), int(h*s)), Image.LANCZOS)
        buf = io.BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()
    except Exception as e:
        print(f"  DICOM->PNG failed: {e}"); return None

# ─────────────────────────────────────────────
def get_prompt(role):
    p   = PATIENT
    hdr = (f"Patient: {p['name']}, DOB {p['dob']}, Age {p['age']}, {p['sex']}. "
           f"Scan: {p['scan_date']}, {p['facility']}. History: {p['known_history']}\n\n")

    # ── WMH / FLAIR ────────────────────────────────────────────────────────────
    if role == "wmh":
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
    "clinical_note": "e.g. posterior distribution suggests small vessel disease; frontal suggests aging"
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
    "frontal_sulcal_width": "normal/mildly widened/moderately widened/severely widened",
    "parietal_sulcal_width": "normal/mildly widened/moderately widened/severely widened",
    "temporal_sulcal_width": "normal/mildly widened/moderately widened/severely widened",
    "dominant_region": "e.g. frontal > parietal, symmetric",
    "clinical_note": "e.g. frontal predominant atrophy pattern"
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

    # ── VESSELS / TOF MRA ──────────────────────────────────────────────────────
    elif role == "vessels":
        return hdr + """Analyse TOF MRA. Patient had basilar dolichoectasia in 2022. Return JSON only — no markdown, no backticks:
{
  "sequence": "TOF_MRA",

  "circle_of_willis": "complete/incomplete",
  "circle_of_willis_missing_segments": ["e.g. AComm, L-PComm"],

  "basilar_artery_diameter_mm": "Xmm",
  "basilar_artery_length_mm": "Xmm (if estimable)",
  "basilar_dolichoectasia": "none/mild/moderate/severe",
  "basilar_vs_2022": "stable/increased/decreased",
  "basilar_flow_signal": "normal/reduced/absent",
  "basilar_cbf_proxy": "normal/mildly reduced/moderately reduced",

  "mca_bilateral": "normal/stenosis",
  "aca_bilateral": "normal/stenosis",
  "pca_bilateral": "normal/stenosis",
  "stenosis_detected": false,
  "stenosis_details": "none",
  "aneurysm": false,
  "overall_vasculature": "normal/abnormal",
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
        return {"error":"no slices","series":series["desc"],"slices_analysed":0}

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
                # Network / DNS failure — wait longer and retry
                wait = 20 * (attempt + 1)
                print(f"  🌐 Network error (attempt {attempt+1}/3) — retrying in {wait}s...")
                time.sleep(wait)
                if attempt == 2:
                    result = {"error": err_str, "slices_analysed": 0}
            elif attempt == 2:
                result = {"error": err_str, "slices_analysed": 0}
            else:
                time.sleep(8)

    result.update(series_name=series["se_name"], series_desc=series["desc"],
                  total_images_in_series=series["n_images"],
                  agent=series["agent"], role=role)
    return result

# ─────────────────────────────────────────────
def sentinel_summary(client, results):
    try:
        findings = json.dumps(results, indent=2)[:30000]
        prompt = f"""You are SENTINEL. Compile MASTER BRAIN HEALTH REPORT v3.
Patient: {PATIENT["name"]} | Age: {PATIENT["age"]} | {PATIENT["scan_date"]}
History: {PATIENT["known_history"]}

RATING SYSTEM — use EXACTLY these four emoji in every Rating column cell and flag list:
  🟢 GREEN  = Normal / within expected range for age
  🟡 YELLOW = Mild deviation / monitor — not urgent
  🟠 ORANGE = Moderate / warrants clinical attention soon
  🔴 RED    = Severe / urgent — requires specialist review

Every table MUST include a "Rating" column with one of those four emoji per row.
Every table MUST include a "Notes" column with a brief clinical interpretation.
Use 🟢🟡🟠🔴 consistently — never use other symbols for ratings.

Include ALL sections below in order:

1. OVERALL RATING — one word (EXCELLENT/GOOD/FAIR/CONCERNING/CRITICAL) + emoji + one-paragraph rationale

2. GREY & WHITE MATTER — table: Parameter | Finding | Normal (Age {PATIENT["age"]}yo Male) | Rating | Notes

3. MTA SCORE & HIPPOCAMPUS — table: Parameter | Left | Right | Asymmetry% | Normal | Rating | Notes
   Include: MTA Score, HOC%, HOC Asymmetry Index

4. MICROVASCULAR DISEASE — table: Parameter | Finding | Normal | Rating | Notes
   Include: Fazekas Periventricular, Fazekas Deep WM, WMH% Burden, Lacunes

5. WMH SPATIAL DISTRIBUTION MAP — table: Region | Finding | Rating | Notes
   Include: Frontal periventricular, Posterior periventricular, Deep frontal, Deep parietal, Deep occipital, Pattern type

6. EPVS / GLYMPHATIC SYSTEM — table: Parameter | Finding | Normal | Rating | Notes
   Include: EPVS grade (basal ganglia), EPVS grade (white matter), Glymphatic implication, Amyloid clearance risk

7. CEREBROVASCULAR — table: Parameter | Finding | Normal | Rating | Notes | vs 2022
   Include: Basilar diameter mm, Basilar length mm, Dolichoectasia severity, CBF proxy, Circle of Willis completeness, Missing segments

8. BRAIN AGE — table: Parameter | Finding | Normal | Rating | Notes
   Include: Estimated brain age, vs chronological age {PATIENT["age"]}

9. CORTICAL ATROPHY + SULCAL MORPHOLOGY — table: Parameter | Finding | Normal | Rating | Notes
   Include: Cortical atrophy grade, Frontal sulcal width, Parietal sulcal width, Temporal sulcal width, Dominant pattern

10. HIPPOCAMPAL ASYMMETRY — table: Parameter | Left | Right | Asymmetry% | Flag (>10%) | Rating | Notes

11. WHITE MATTER TRACT INTEGRITY — table: Tract | Integrity | Normal | Rating | Notes
    Include: Corpus callosum, Corticospinal tract, SLF, Cingulum, Overall FA impression
    If DWI/DTI not available, state so clearly in a note above the table.

12. RED FLAGS 🔴 — bullet list, urgent items only
13. ORANGE FLAGS 🟠 — bullet list, moderate items needing attention
14. YELLOW FLAGS 🟡 — bullet list, mild monitoring items
15. GREEN FLAGS 🟢 — bullet list, normal/positive findings
16. TOP 5 RECOMMENDED ACTIONS — numbered, most urgent first
17. FREESURFER RECOMMENDATION — one paragraph
18. COMPARISON NOTE re 2022 MRI — table or bullet list: basilar artery, WMH, hippocampus

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
        f.write(f"  BRAIN MRI v3 — {PATIENT['name']} | Age {PATIENT['age']}\n")
        f.write(f"  History: {PATIENT['known_history']}\n")
        f.write(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"  Series: {stats['series_ok']}/{stats['series_total']} | "
                f"Total images: {stats['total_images']} | Slices to AI: {stats['slices_sent']}\n")
        f.write("="*70+"\n\n"+sentinel+"\n\n")
        for i, r in enumerate(results, 1):
            f.write(f"{'─'*60}\n{i}. {r.get('series_desc','?')} | "
                    f"{r.get('total_images_in_series','?')} imgs | "
                    f"{r.get('slices_analysed','?')} slices sent\n{'─'*60}\n")
            clean = {k:v for k,v in r.items()
                     if k not in ("series_name","series_desc","agent","role",
                                  "total_images_in_series","slices_analysed")}
            f.write(json.dumps(clean, indent=2)+"\n\n")
        f.write("="*70+"\n⚕️ AI only — review with neurologist.\n"+"="*70+"\n")

# ─────────────────────────────────────────────
def write_html(results, sentinel, path, stats):
    import html as hl, re
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    # ── markdown → HTML ────────────────────────────────────────────────────────
    def apply_emoji_badges(text):
        """Replace rating emoji with coloured pill badges anywhere in text."""
        text = text.replace("🔴", "<span class='badge-red'>🔴 Urgent</span>")
        text = text.replace("🟠", "<span class='badge-orange'>🟠 Warning</span>")
        text = text.replace("🟡", "<span class='badge-yellow'>🟡 Mild</span>")
        text = text.replace("🟢", "<span class='badge-green'>🟢 Normal</span>")
        return text

    def md2h(t):
        o         = []
        in_table  = False
        in_list   = False
        header_done = False

        for raw_line in t.split("\n"):
            l = raw_line

            # headings
            if l.startswith("### "):
                if in_list:  o.append("</ul>"); in_list = False
                if in_table: o.append("</table>"); in_table = False
                o.append(f'<h3>{hl.escape(l[4:])}</h3>'); header_done = True; continue
            if l.startswith("## "):
                if in_list:  o.append("</ul>"); in_list = False
                if in_table: o.append("</table>"); in_table = False
                o.append(f'<h2>{hl.escape(l[3:])}</h2>'); header_done = True; continue
            if l.startswith("# "):
                if in_list:  o.append("</ul>"); in_list = False
                if in_table: o.append("</table>"); in_table = False
                o.append(f'<h1>{hl.escape(l[2:])}</h1>'); header_done = True; continue

            # tables
            if l.startswith("|"):
                cells = [c.strip() for c in l.split("|")[1:-1]]
                if all(set(c) <= set("-: ") for c in cells):
                    continue                          # separator row
                if not in_table:
                    o.append("<table>"); in_table = True; is_first_row = True
                else:
                    is_first_row = False
                tag = "th" if is_first_row else "td"
                colored = []
                for c in cells:
                    cu = c.upper()
                    # colour the cell text by rating content
                    if tag == "td":
                        if "🔴" in c:
                            cell_class = " class='val-red'"
                        elif "🟠" in c:
                            cell_class = " class='val-orange'"
                        elif "🟡" in c:
                            cell_class = " class='val-yellow'"
                        elif "🟢" in c:
                            cell_class = " class='val-green'"
                        elif any(x in cu for x in ["SEVERE","CRITICAL","URGENT"]):
                            cell_class = " class='val-red'"
                        elif any(x in cu for x in ["MODERATE","WARNING"]):
                            cell_class = " class='val-orange'"
                        elif any(x in cu for x in ["MILD","BORDERLINE","INCOMPLETE"]):
                            cell_class = " class='val-yellow'"
                        elif any(x in cu for x in ["NORMAL","NONE","COMPLETE","YOUNGER","ABSENT"]):
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

            # lists
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

            # horizontal rule
            if l.strip() in ("---", "***", "___"):
                o.append("<hr>"); continue

            # paragraph / inline formatting
            if l.strip():
                l2 = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", l)
                l2 = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",         l2)
                l2 = apply_emoji_badges(hl.escape(l2))
                o.append(f"<p>{l2}</p>")

        if in_list:  o.append("</ul>")
        if in_table: o.append("</table>")
        return "\n".join(o)

    sh = md2h(sentinel)

    # ── per-series cards ───────────────────────────────────────────────────────
    ROLE_LABELS = {
        "wmh":       "🧠 WMH / Glymphatic",
        "t1volume":  "📐 Volume / Atrophy",
        "vessels":   "🩸 Cerebrovascular",
        "dwi":       "🔬 Diffusion / Tracts",
        "t2struct":  "🔍 T2 Structure",
        "pdf_report":"📄 Report PDF",
    }

    def val_color(k, v):
        sv = str(v).upper()
        if any(x in sv for x in ["SEVERE","CRITICAL","TRUE","SIGNIFICANTLY","HIGH RISK"]):
            return "style='color:#f85149;font-weight:bold'"
        if any(x in sv for x in ["MODERATE","MILD","AMBER","BORDERLINE","INTERMEDIATE"]):
            return "style='color:#d29922;font-weight:bold'"
        if any(x in sv for x in ["NORMAL","NONE","FALSE","GREEN","YOUNGER","COMPLETE"]):
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
        "wmh_pct_estimate","wmh_burden","wmh_spatial_distribution",
        "epvs_grade_basal_ganglia","epvs_grade_white_matter","epvs_amyloid_clearance_risk",
        "mta_score_left","mta_score_right","mta_asymmetry_pct","mta_asymmetry_flag",
        "hippocampal_occupancy_hoc","hoc_left_pct","hoc_right_pct","hoc_asymmetry_pct","hoc_asymmetry_flag",
        "sulcal_morphology","regional_atrophy",
        "basilar_artery_diameter_mm","basilar_artery_length_mm","basilar_cbf_proxy",
        "circle_of_willis_missing_segments",
        "white_matter_tract_integrity",
        "brain_age_estimate","brain_age_vs_chronological",
    }

    # Reference ranges for a 69-year-old male (evidence-based)
    NORMAL_RANGES = {
        # WMH / FLAIR
        "wmh_periventricular_fazekas": "0–1 (age-related)",
        "wmh_deep_fazekas":            "0 (none expected)",
        "wmh_burden":                  "NONE or MILD",
        "wmh_pct_estimate":            "< 1–2% of WM volume",
        "lacunes":                     "False (none expected)",
        "lacune_count":                "0",
        "enlarged_perivascular_spaces_epvs": "NONE to MILD",
        "epvs_grade_basal_ganglia":    "0–1",
        "epvs_grade_white_matter":     "0–1",
        "epvs_glymphatic_implication": "normal",
        "epvs_amyloid_clearance_risk": "low",
        "age_comparison":              "average for age 69",
        # T1 volume
        "grey_matter_pct":             "~42–46% (declines ~0.5%/yr after 50)",
        "white_matter_pct":            "~40–46%",
        "csf_pct":                     "~10–16%",
        "gm_status":                   "NORMAL",
        "cortical_atrophy_grade":      "0–1 (none to mild acceptable)",
        "mta_score_left":              "≤ 1.5 (normal for age 69)",
        "mta_score_right":             "≤ 1.5 (normal for age 69)",
        "mta_asymmetry_pct":           "< 10% L vs R",
        "hippocampal_occupancy_hoc":   "> 60%",
        "hoc_left_pct":                "> 60%",
        "hoc_right_pct":               "> 60%",
        "hoc_asymmetry_pct":           "< 10% L vs R",
        "ventricular_size":            "normal",
        "brain_age_estimate":          "≈ 69 years (chronological)",
        "brain_age_vs_chronological":  "same or younger",
        # Vessels
        "basilar_artery_diameter_mm":  "3.0–4.5 mm",
        "basilar_dolichoectasia":      "none",
        "basilar_flow_signal":         "normal",
        "basilar_cbf_proxy":           "normal",
        "circle_of_willis":            "complete",
        "mca_bilateral":               "normal",
        "aca_bilateral":               "normal",
        "pca_bilateral":               "normal",
        "stenosis_detected":           "False",
        "aneurysm":                    "False",
        # T2 struct
        "basal_ganglia":               "normal",
        "cerebellum":                  "normal",
        "focal_lesions":               "False",
        # DWI
        "acute_infarction":            "False",
    }

    cards = ""
    for r in results:
        # Skip pdf_report cards — they never have slices and add noise
        if r.get("role") == "pdf_report":
            continue

        ok    = "error" not in r or "raw_analysis" in r
        badge = f'<span class="badge {"ok" if ok else "err"}">{"✓" if ok else "✗"}</span>'
        role  = r.get("role","")
        label = ROLE_LABELS.get(role, role)

        # If the series errored, show a compact error card
        if not ok and "raw_analysis" not in r:
            err_msg = r.get("error","unknown error")
            cards += f"""
<div class='card card-error'>
  <div class='card-header'>
    {badge}
    <span class='role-label'>{label}</span>
    <strong>{hl.escape(r.get('series_desc','?'))}</strong>
    <span class='meta'>{r.get('series_name','?')} | {r.get('total_images_in_series','?')} imgs | Agent: {r.get('agent','?')}</span>
  </div>
  <div class='error-body'>⚠️ Series could not be analysed: <code>{hl.escape(err_msg)}</code><br>
  <em>If this is a network error, re-run the script — the retry logic will attempt recovery.</em></div>
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
      <th class='ref-col'>Normal Range (Age 69 Male)</th>
    </tr>
    {rows}
  </table>
</div>"""

    # ── full HTML ──────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Brain MRI v3 — {PATIENT["name"]}</title>
<style>
:root{{
  --bg:#0d1117; --s:#161b22; --b:#30363d; --t:#e6edf3; --m:#8b949e;
  --a:#58a6ff;  --g:#3fb950; --y:#d29922; --r:#f85149;
  --highlight-bg:#1c2333;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--t);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.6;padding:2rem}}

/* ── header ── */
.hdr{{background:linear-gradient(135deg,#1a237e,#0d47a1);border-radius:12px;padding:2rem;margin-bottom:2rem}}
.hdr h1{{font-size:1.8rem;color:#fff;margin-bottom:.5rem}}
.hdr .m{{color:#90caf9;font-size:.9rem}}
.version-badge{{display:inline-block;background:#3949ab;color:#e8eaf6;font-size:.75rem;padding:.15rem .5rem;border-radius:4px;margin-left:.5rem;vertical-align:middle}}

/* ── stat bar ── */
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}}
.stat{{background:var(--s);border:1px solid var(--b);border-radius:8px;padding:1rem;text-align:center}}
.stat .v{{font-size:2rem;font-weight:700;color:var(--a)}}
.stat .l{{font-size:.8rem;color:var(--m)}}

/* ── sections ── */
.sec{{background:var(--s);border:1px solid var(--b);border-radius:12px;padding:1.5rem;margin-bottom:1.5rem}}
h1{{color:var(--a);font-size:1.5rem;margin:1rem 0 .5rem}}
h2{{color:var(--a);font-size:1.2rem;margin:1rem 0 .5rem;border-bottom:1px solid var(--b);padding-bottom:.5rem}}
h3{{color:#79c0ff;font-size:1rem;margin:.8rem 0 .3rem}}
p{{margin:.5rem 0}}
li{{margin:.25rem 0 .25rem 1.5rem}}
strong{{color:#f0f6fc}}
em{{color:var(--m)}}
hr{{border:none;border-top:1px solid var(--b);margin:1rem 0}}

/* ── tables (sentinel) ── */
table{{width:100%;border-collapse:collapse;margin:.5rem 0;font-size:.9rem}}
th{{background:#21262d;color:var(--a);padding:.5rem;text-align:left}}
td{{padding:.4rem .5rem;border-bottom:1px solid var(--b);vertical-align:top;word-break:break-word}}
tr:hover td{{background:#21262d}}

/* ── sentinel table value colours ── */
.val-red{{color:var(--r);font-weight:600}}
.val-orange{{color:#f0883e;font-weight:600}}
.val-yellow{{color:var(--y);font-weight:600}}
.val-green{{color:var(--g)}}

/* ── inline rating badge pills ── */
.badge-red{{display:inline-block;background:#3d0e0e;color:#f85149;border:1px solid #f8514955;
           border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700;white-space:nowrap}}
.badge-orange{{display:inline-block;background:#2d1a08;color:#f0883e;border:1px solid #f0883e55;
              border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700;white-space:nowrap}}
.badge-yellow{{display:inline-block;background:#2d2008;color:#d29922;border:1px solid #d2992255;
              border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700;white-space:nowrap}}
.badge-green{{display:inline-block;background:#0d2818;color:#3fb950;border:1px solid #3fb95055;
             border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700;white-space:nowrap}}

/* ── cards ── */
.card{{background:#0d1117;border:1px solid var(--b);border-radius:10px;margin-bottom:1rem;overflow:hidden}}
.card-header{{background:var(--s);padding:.75rem 1rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}}
.badge{{padding:.2rem .5rem;border-radius:4px;font-size:.8rem;font-weight:700}}
.badge.ok{{background:#1a472a;color:var(--g)}}
.badge.err{{background:#4a1a1a;color:var(--r)}}
.role-label{{font-size:.8rem;background:#21262d;color:#79c0ff;padding:.15rem .4rem;border-radius:4px}}
.meta{{color:var(--m);font-size:.8rem;margin-left:auto}}

/* ── card table ── */
.card table td.key-col{{color:var(--m);width:28%;font-size:.82rem;font-family:monospace}}
.card table th.key-col{{color:#79c0ff;font-size:.82rem;width:28%}}
.card table td.ref-col{{color:#6e7681;font-size:.8rem;width:28%;font-style:italic;border-left:1px solid var(--b);padding-left:.6rem}}
.card table th.ref-col{{color:#79c0ff;font-size:.82rem;border-left:1px solid var(--b);padding-left:.6rem}}
.ref-na{{opacity:.3}}
.highlight-row td{{background:var(--highlight-bg)!important;border-left:3px solid var(--a)}}
.highlight-row td.key-col{{color:#79c0ff}}
.card-error .error-body{{padding:.75rem 1rem;font-size:.88rem;color:var(--y)}}
.card-error .error-body code{{background:#21262d;padding:.1rem .3rem;border-radius:3px;color:var(--r);font-size:.82rem}}

/* ── sub-tables (nested dicts) ── */
.sub-table{{background:#0d1117;margin:0;border:none;font-size:.82rem}}
.sub-table td{{border-bottom:1px solid #21262d;padding:.25rem .4rem}}
.sub-table .sub-key{{color:var(--m);width:45%;font-style:italic}}
.inline-list{{margin:.25rem 0 .25rem 1rem;font-size:.85rem}}

/* ── disclaimer ── */
.disc{{background:#1a0a0a;border:1px solid #f8514933;border-radius:8px;padding:1rem;
       color:var(--r);font-size:.85rem;margin-top:2rem}}

/* ── new feature callout ── */
.new-features{{background:#0d2137;border:1px solid #1f4a7a;border-radius:8px;
               padding:.75rem 1rem;margin-bottom:1.5rem;font-size:.85rem;color:#90caf9}}
.new-features strong{{color:#58a6ff}}
</style>
</head>
<body>

<!-- header -->
<div class="hdr">
  <h1>🧠 Brain MRI Analysis Report <span class="version-badge">v3 — Enhanced Radiomic</span></h1>
  <div class="m">
    <strong>{PATIENT["name"]}</strong> | DOB: {PATIENT["dob"]} | Age: {PATIENT["age"]} | {PATIENT["sex"]}<br>
    Scan: {PATIENT["scan_date"]} | {PATIENT["facility"]}<br>
    History: {PATIENT["known_history"]}<br>
    Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | AI: Google {MODEL}
  </div>
</div>

<!-- new feature callout -->
<div class="new-features">
  <strong>v3 New Radiomic Features:</strong>
  WMH Spatial Distribution Map &nbsp;|&nbsp;
  EPVS Grading by Location + Amyloid Clearance Risk &nbsp;|&nbsp;
  Hippocampal Asymmetry Index (L vs R) &nbsp;|&nbsp;
  Sulcal Morphology by Region &nbsp;|&nbsp;
  Basilar CBF Proxy + Circle of Willis Missing Segments &nbsp;|&nbsp;
  White Matter Tract Integrity (DTI/DWI)
</div>

<!-- stat bar -->
<div class="stats">
  <div class="stat"><div class="v">{stats["series_ok"]}/{stats["series_total"]}</div><div class="l">Series Analysed</div></div>
  <div class="stat"><div class="v">{stats["total_images"]}</div><div class="l">Total DICOM Images</div></div>
  <div class="stat"><div class="v">{stats["slices_sent"]}</div><div class="l">Slices Sent to AI</div></div>
  <div class="stat"><div class="v">{stats["series_total"]}</div><div class="l">Priority Series Found</div></div>
</div>

<!-- sentinel master report -->
<div class="sec"><h2>🛡️ SENTINEL Master Report v3</h2>{sh}</div>

<!-- per-series detail -->
<div class="sec"><h2>🔬 Detailed Per-Series Findings</h2>{cards}</div>

<!-- disclaimer -->
<div class="disc">
  ⚕️ <strong>CLINICAL DISCLAIMER:</strong> AI-generated analysis only.
  All findings must be reviewed and validated by a qualified neurologist or radiologist
  before any clinical decision is made. This report does not constitute a medical diagnosis.
</div>

</body>
</html>"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

# ─────────────────────────────────────────────
def main():
    print(f"\n{'='*60}\n  🧠 HEALTH DIGITAL WORKFORCE v3 — Enhanced Radiomic\n"
          f"  {PATIENT['name']} | Age {PATIENT['age']} | {PATIENT['known_history']}\n{'='*60}\n")

    client = setup()
    print("\n📂 Scanning DICOM series...")
    series_list = discover_series()
    if not series_list:
        print("No priority series found."); sys.exit(0)

    print(f"\n✓ {len(series_list)} series found:")
    for s in series_list:
        print(f"  {s['se_name']} | {s['desc']} | {s['n_images']} imgs → {s['agent']}")
    print()

    results      = []
    total_images = sum(s["n_images"] for s in series_list)
    slices_sent  = 0

    for s in series_list:
        print(f"🔬 {s['se_name']} {s['desc']} ({s['n_images']} images)...")
        r = analyse(client, s)
        results.append(r)
        slices_sent += r.get("slices_analysed", 0)
        ok = "error" not in r or "raw_analysis" in r
        print(f"  {'✓' if ok else '✗'} Done — {r.get('slices_analysed',0)} slices sent")
        time.sleep(8)   # longer gap to avoid connection throttling

    stats = dict(
        series_ok     = sum(1 for r in results if "error" not in r or "raw_analysis" in r),
        series_total  = len(results),
        total_images  = total_images,
        slices_sent   = slices_sent,
    )

    print("\n🛡️  SENTINEL v3 compiling...")
    master = sentinel_summary(client, results)

    write_txt(results, master, OUTPUT_TXT, stats)
    write_html(results, master, OUTPUT_HTML, stats)

    print(master[:2000])
    print(f"\n✅ TXT:  {OUTPUT_TXT}\n   HTML: {OUTPUT_HTML}\n   Stats: {stats}\n")

if __name__ == "__main__":
    main()
