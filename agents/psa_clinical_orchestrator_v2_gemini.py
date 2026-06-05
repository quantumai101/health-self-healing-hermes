"""
PSA Clinical Ensemble Orchestrator v2 — Gemini Edition
=======================================================
Replaces the chargeable Anthropic Claude API with the FREE
Google Gemini API (gemini-2.0-flash or gemini-1.5-pro).

Requirements:
    pip install google-generativeai reportlab

.env setup (your line 10 is CORRECT — see confirmation below):
    GEMINI_API_KEY=<your key from aistudio.google.com>
    MEDICAL_REPORTS_PATH="I:\\PSA Clinical analysis reports"

Usage:
    python psa_clinical_orchestrator_v2_gemini.py

Output:
    • psa_clinical_report_v2.txt   — plain text synthesis
    • PSA_Clinical_Report_DarkMode.pdf  — formatted dark-mode PDF
      Both saved to the path in MEDICAL_REPORTS_PATH (.env) or cwd.
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path

# ── load .env manually (no python-dotenv needed) ────────────────────────────
def load_dotenv(env_path=".env"):
    """Simple .env loader — no external dependency."""
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key not in os.environ:        # don't overwrite existing env vars
                os.environ[key] = val

load_dotenv()

# ── Gemini import ─────────────────────────────────────────────────────────────
try:
    import google.generativeai as genai
except ImportError:
    print("❌  google-generativeai not installed. Run:")
    print("    pip install google-generativeai")
    sys.exit(1)

# ── reportlab import (optional — PDF generation) ────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable)
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False
    print("⚠️   reportlab not found — PDF will be skipped. Run:  pip install reportlab")

# ── constants ────────────────────────────────────────────────────────────────
MANIFEST_FILE = "psa_metrics_manifest.json"
TXT_REPORT    = "psa_clinical_report_v2.txt"
PDF_REPORT    = "PSA_Clinical_Report_DarkMode.pdf"

# ── sample manifest (pre-filled with your data) ──────────────────────────────
SAMPLE_MANIFEST = {
    "patient_metadata": {
        "name": "Zhang Zhi Ming", "dob": "14/03/1955",
        "age_years": 71, "gender": "Male",
        "address": "Parramatta NSW 2150"
    },
    "psa_history": [
        {"date": "28-Dec-22", "total_psa": 3.3, "free_psa": 1.2, "free_pct": 36},
        {"date": "03-Jan-24", "total_psa": 4.2, "free_psa": 1.3, "free_pct": 31},
        {"date": "17-Feb-26", "total_psa": 5.4, "free_psa": None, "free_pct": None},
        {"date": "01-May-26", "total_psa": 8.4, "free_psa": 1.9,  "free_pct": 23},
    ],
    "prostate_imaging": [
        {"date": "22/10/2025", "volume_ml": 99.9, "dims": "5.8x6.0x5.4 cm",
         "pvr_ml": 79,  "notes": "Calcification 4x6mm; cyst 9mm"},
        {"date": "28/04/2026", "volume_ml": 61.0, "dims": "4.6x4.6x5.5 cm",
         "pvr_ml": 90,  "notes": "Only right ureteric jet seen; left absent"},
    ],
    "psad": {"oct25": 0.054, "may26": 0.138, "threshold": 0.15},
    "iron_17feb26": {
        "iron_umoll": 10.7, "prev_iron": 16.4,
        "saturation_pct": 21, "ferritin_ugl": 70
    },
    "inflammation": {"crp_feb26": 0.4, "crp_oct25": 1.7},
    "lipids_feb26": {
        "total_chol": 6.4, "hdl": 1.4, "ldl": 4.8,
        "trig": 0.6, "tc_hdl_ratio": 4.57
    },
    "metabolic": {
        "egfr": 74, "creatinine": 90, "globulin": 22,
        "borderline_ogtt_date": "29/10/2025"
    },
    "ctca_hermes_v2": {
        "pLAD_FAI_HU": -68.4, "threshold_HU": -70.1,
        "status": "BORDERLINE ELEVATED",
        "cad_rads": "CAD-RADS 2 + FAI modifier",
        "agatston": 50, "ef_pct": 58.2,
        "lv_mass_index": 102.1
    },
    "pending": ["MRI Prostate (requested 11/05/2026)", "HbA1c", "Urine microalbumin", "MSU"]
}


# ── helpers ──────────────────────────────────────────────────────────────────
def load_or_create_manifest(path: str) -> dict:
    if not os.path.exists(path):
        print(f"⚠️  Manifest not found — writing sample to {path}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_MANIFEST, f, indent=2)
        return SAMPLE_MANIFEST
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_output_dir() -> Path:
    """Use MEDICAL_REPORTS_PATH from .env if set, else cwd."""
    env_path = os.environ.get("MEDICAL_REPORTS_PATH", "").strip().strip('"')
    if env_path:
        p = Path(env_path)
        try:
            p.mkdir(parents=True, exist_ok=True)
            return p
        except Exception as e:
            print(f"⚠️  Cannot write to MEDICAL_REPORTS_PATH ({env_path}): {e}")
            print("   Falling back to current directory.")
    return Path(os.getcwd())


def build_prompt(m: dict) -> str:
    ph  = m["psa_history"]
    lat = ph[-1]
    return f"""You are a senior urological oncology consultant.
A 71-year-old male presents with a sudden PSA rise.

PSA HISTORY:
{json.dumps(ph, indent=2)}

Latest PSA: {lat['total_psa']} µg/L  |  Free PSA: {lat.get('free_psa')} µg/L  |  Free/Total: {lat.get('free_pct')}%
PSA velocity: +3.0 µg/L over 73 days (17-Feb-26 → 01-May-26)

PROSTATE IMAGING:
  Oct-2025: volume 99.9 mL, PVR 79 mL → PSAD 0.054
  Apr-2026: volume 61.0 mL, PVR 90 mL → PSAD 0.138 (threshold 0.15)
  Apr-2026: Only right ureteric jet seen; left jet ABSENT

LABS (17-Feb-26):
  Iron: 10.7 µmol/L (dropped from 16.4 — "big drop")
  CRP: 0.4 mg/L (was 1.7 mg/L Oct-25)
  LDL: {m['lipids_feb26']['ldl']} mmol/L (elevated)
  Globulin: {m['metabolic']['globulin']} g/L (slightly low)
  eGFR: {m['metabolic']['egfr']} mL/min
  Borderline OGTT: {m['metabolic']['borderline_ogtt_date']}

CTCA (HERMES v2):
  pLAD FAI: {m['ctca_hermes_v2']['pLAD_FAI_HU']} HU (threshold {m['ctca_hermes_v2']['threshold_HU']} HU) — {m['ctca_hermes_v2']['status']}
  CAD-RADS: {m['ctca_hermes_v2']['cad_rads']}
  Agatston: {m['ctca_hermes_v2']['agatston']}  |  EF: {m['ctca_hermes_v2']['ef_pct']}%

PENDING: {', '.join(m['pending'])}

Write a structured urological assessment with EXACTLY these 5 sections:

1. PSA TREND ANALYSIS — velocity, doubling time, free/total ratio significance
2. PSA DENSITY RECONCILIATION — explain 99.9 vs 61 mL discrepancy; which PSAD is reliable
3. DIFFERENTIAL DIAGNOSIS — ranked with evidence (BPH, prostatitis, obstruction, malignancy)
4. CTCA / SYSTEMIC INFLAMMATION — does pLAD FAI directly raise PSA? Indirect pathways?
5. PRIORITISED NEXT STEPS — with clinical justification

Be concise and quantitative. Use clinical terminology. No disclaimers."""


# ── Gemini synthesis ──────────────────────────────────────────────────────────
def run_gemini(prompt: str, api_key: str) -> str:
    genai.configure(api_key=api_key)

    # Try gemini-2.0-flash first (free tier), fall back to gemini-1.5-flash
    for model_name in ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]:
        try:
            print(f"   Trying model: {model_name} ...")
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=(
                    "You are a board-certified Urological Oncology Consultant. "
                    "Respond only with a formal structured clinical assessment. "
                    "No disclaimers. Quantify every finding."
                )
            )
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.15,
                    max_output_tokens=2000,
                )
            )
            print(f"   ✅ Success with {model_name}")
            return response.text
        except Exception as e:
            print(f"   ⚠️  {model_name} failed: {e}")
            continue

    raise RuntimeError("All Gemini models failed. Check your GEMINI_API_KEY.")


# ── simple dark-mode PDF (reportlab) ─────────────────────────────────────────
def build_pdf(report_text: str, output_path: Path, manifest: dict):
    if not REPORTLAB_OK:
        return
    from reportlab.platypus import Preformatted
    from reportlab.lib.styles import getSampleStyleSheet

    BG    = colors.HexColor("#0D1117")
    PANEL = colors.HexColor("#161B22")
    ACCENT= colors.HexColor("#58A6FF")
    TEXT  = colors.HexColor("#E6EDF3")
    GOLD  = colors.HexColor("#E3B341")
    TSEC  = colors.HexColor("#8B949E")
    W, H  = A4

    def draw_bg(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BG)
        canvas.rect(0, 0, W, H, fill=1, stroke=0)
        canvas.setFillColor(PANEL)
        canvas.rect(0, H - 28*mm, W, 28*mm, fill=1, stroke=0)
        canvas.setStrokeColor(ACCENT)
        canvas.setLineWidth(1)
        canvas.line(0, H - 28*mm, W, H - 28*mm)
        canvas.setStrokeColor(colors.HexColor("#30363D"))
        canvas.setLineWidth(0.5)
        canvas.line(14*mm, 10*mm, W - 14*mm, 10*mm)
        canvas.setFillColor(TSEC)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(14*mm, 7*mm,
            "HERMES CLINICAL ENSEMBLE PORTAL  •  PSA DIAGNOSTIC REPORT  •  CONFIDENTIAL")
        canvas.drawRightString(W-14*mm, 7*mm, f"Page {doc.page}")
        canvas.restoreState()

    def S(name, **kw):
        defaults = dict(fontName="Helvetica", fontSize=9,
                        textColor=TEXT, leading=13, spaceAfter=2)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    doc = SimpleDocTemplate(str(output_path), pagesize=A4,
                            leftMargin=14*mm, rightMargin=14*mm,
                            topMargin=12*mm, bottomMargin=14*mm)
    story = [Spacer(1, 22*mm)]
    story.append(Paragraph("HERMES // PSA DIAGNOSTIC PORTAL", S("T",
        fontName="Helvetica-Bold", fontSize=20, textColor=ACCENT, alignment=TA_CENTER)))
    story.append(Paragraph(
        "MULTI-AGENT CLINICAL ENSEMBLE PIPELINE VER. 2.0 — GEMINI EDITION — DARK MODE",
        S("SH", fontSize=7.5, textColor=TSEC, alignment=TA_CENTER)))
    story.append(Spacer(1, 5*mm))

    # Synthesis body
    for line in report_text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 2*mm))
        elif line.startswith(("1.", "2.", "3.", "4.", "5.")):
            story.append(Paragraph(line, S("sec", fontName="Helvetica-Bold",
                fontSize=9, textColor=ACCENT, spaceBefore=4)))
            story.append(HRFlowable(width="100%", thickness=0.4,
                color=colors.HexColor("#30363D")))
        else:
            story.append(Paragraph(line, S("body", fontSize=8.5,
                textColor=TEXT, leading=12)))

    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        f"GENERATED BY HERMES CLINICAL ENSEMBLE v2.0  |  MODEL: Gemini API (Free)  |  "
        f"REPORT DATE: {datetime.now().strftime('%Y-%m-%d')}",
        S("ft", fontSize=7, textColor=TSEC, alignment=TA_CENTER)))

    doc.build(story, onFirstPage=draw_bg, onLaterPages=draw_bg)
    print(f"📄  PDF saved: {output_path}")


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("🔬  PSA CLINICAL ENSEMBLE ORCHESTRATOR v2 — GEMINI EDITION")
    print(f"    {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 70)

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("❌  GEMINI_API_KEY not set.")
        print("    Add it to your .env file:  GEMINI_API_KEY=AIza...")
        print("    Get a free key at: https://aistudio.google.com/app/apikey")
        sys.exit(1)

    manifest = load_or_create_manifest(MANIFEST_FILE)
    print("✅  Manifest loaded")

    prompt = build_prompt(manifest)
    print("🚀  Calling Gemini API (free tier) ...")

    try:
        report_text = run_gemini(prompt, api_key)
    except Exception as e:
        print(f"❌  Gemini error: {e}")
        sys.exit(1)

    out_dir   = resolve_output_dir()
    txt_path  = out_dir / TXT_REPORT
    pdf_path  = out_dir / PDF_REPORT

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(f"PSA Clinical Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write("=" * 70 + "\n\n")
        f.write(report_text)

    print(f"\n🏁  SYNTHESIS COMPLETE")
    print(f"📝  Text report: {txt_path}")
    print("=" * 70)
    print(report_text)
    print("=" * 70)

    # PDF
    build_pdf(report_text, pdf_path, manifest)
    print(f"\n✅  All outputs written to: {out_dir}")


if __name__ == "__main__":
    main()
