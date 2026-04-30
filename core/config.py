"""
core/config.py
All constants, thresholds, and model IDs.
AGENTS.md Section 7 & 8 — Single Source of Truth.
No agent may hardcode these values.
"""

# ---------------------------------------------------------------------------
# GEMINI MODEL FALLBACK CHAIN  (AGENTS.md Section 5)
# ---------------------------------------------------------------------------
GEMINI_MODELS = [
    ("gemini-3-flash-preview",        "Gemini 3 Flash"),
    ("gemini-3.1-flash-lite-preview", "Gemini 3.1 Flash-Lite"),
    ("gemini-2.5-flash",              "Gemini 2.5 Flash"),
]
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MAX_TOKENS = 2048
GEMINI_TEMPERATURE = 0.4
GEMINI_RETRY_ATTEMPTS = 2
GEMINI_RETRY_CODES = {429, 503, 502, 504}

# ---------------------------------------------------------------------------
# BMI THRESHOLDS  (AGENTS.md Section 7)
# ---------------------------------------------------------------------------
BMI_UNDERWEIGHT = 18.5
BMI_NORMAL_MAX  = 24.9
BMI_OVERWEIGHT  = 25.0
BMI_OBESE_I     = 30.0
BMI_OBESE_II    = 35.0
BMI_OBESE_III   = 40.0

BMI_BANDS = {
    "Underweight": (0,      BMI_UNDERWEIGHT),
    "Normal":      (BMI_UNDERWEIGHT, BMI_OVERWEIGHT),
    "Overweight":  (BMI_OVERWEIGHT,  BMI_OBESE_I),
    "Obese I":     (BMI_OBESE_I,     BMI_OBESE_II),
    "Obese II":    (BMI_OBESE_II,    BMI_OBESE_III),
    "Obese III":   (BMI_OBESE_III,   999),
}

BMI_DISEASE_MAP = {
    "Underweight": "Malnutrition, osteoporosis, immune deficiency",
    "Normal":      "Healthy — routine monitoring",
    "Overweight":  "Hypertension onset, pre-diabetes risk",
    "Obese I":     "Cardiovascular disease, type 2 diabetes, sleep apnoea",
    "Obese II":    "Metabolic syndrome, severe cardiovascular events",
    "Obese III":   "Heart failure, stroke — critical intervention required",
}

BMI_COLORS = {
    "Underweight": "#60a5fa",
    "Normal":      "#22c55e",
    "Overweight":  "#f59e0b",
    "Obese I":     "#f97316",
    "Obese II":    "#ef4444",
    "Obese III":   "#7f1d1d",
}

# ---------------------------------------------------------------------------
# BLOOD PRESSURE THRESHOLDS  (mmHg systolic)
# ---------------------------------------------------------------------------
BP_NORMAL    = 120
BP_ELEVATED  = 130
BP_STAGE1    = 140
BP_CRISIS    = 180

BP_STAGES = ["Normal", "Elevated", "Stage 1 HTN", "Stage 2 HTN", "HTN Crisis"]
BP_COLORS = {
    "Normal":      "#22c55e",
    "Elevated":    "#84cc16",
    "Stage 1 HTN": "#f59e0b",
    "Stage 2 HTN": "#ef4444",
    "HTN Crisis":  "#7f1d1d",
}

# ---------------------------------------------------------------------------
# GLUCOSE THRESHOLDS  (mmol/L fasting)
# ---------------------------------------------------------------------------
GLUCOSE_NORMAL      = 5.6
GLUCOSE_PREDIABETIC = 7.0

GLUCOSE_STAGES = ["Normal", "Pre-diabetic", "Diabetic"]
GLUCOSE_COLORS = {
    "Normal":      "#22c55e",
    "Pre-diabetic":"#f59e0b",
    "Diabetic":    "#ef4444",
}

# ---------------------------------------------------------------------------
# HbA1c THRESHOLDS  (%)
# ---------------------------------------------------------------------------
HBA1C_NORMAL      = 5.7
HBA1C_PREDIABETIC = 6.5

# ---------------------------------------------------------------------------
# RISK SCORE BANDS
# ---------------------------------------------------------------------------
RISK_LOW      = 0.30
RISK_MODERATE = 0.60
RISK_HIGH     = 0.80

STATUS_COLORS = {
    "OK":       "#22c55e",
    "REVIEW":   "#f59e0b",
    "CRITICAL": "#ef4444",
}

# ---------------------------------------------------------------------------
# UI THEME  (AGENTS.md Section 8)
# ---------------------------------------------------------------------------
UI_BG          = "#060b18"
UI_SIDEBAR_BG  = "#0a1120"
UI_ACCENT      = "#38bdf8"
UI_USER_MSG_BG = "#1a2f55"
UI_AGENT_MSG_BG= "#0f172a"
UI_FONT_MONO   = "JetBrains Mono"
UI_FONT_DISPLAY= "Share Tech Mono"

UI_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono&family=Share+Tech+Mono&display=swap');
    html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace !important; }
    h1, h2, h3, h4 { font-family: 'Share Tech Mono', sans-serif !important; color: #38bdf8 !important; text-transform: uppercase; }
    .stApp { background: #060b18; }
    [data-testid="stSidebar"] { background: #0a1120 !important; border-right: 1px solid #1e293b; }
    .user-msg  { background: #1a2f55; border-radius: 10px; padding: 12px; margin: 6px 0; border: 1px solid #3b82f6; color: #e2e8f0; }
    .agent-msg { background: #0f172a; border-left: 4px solid #38bdf8; padding: 12px; margin: 6px 0; color: #cbd5e1; }
    .disclaimer { background: #1a1a2e; border: 1px solid #f59e0b; border-radius: 8px; padding: 10px; color: #f59e0b; font-size: 0.85rem; margin: 8px 0; }
</style>
"""

# ---------------------------------------------------------------------------
# APP METADATA
# ---------------------------------------------------------------------------
APP_TITLE   = "Health AI — Hermes"
APP_ICON    = "🏥"
APP_VERSION = "2.0.0"

DB_PATH  = "/tmp/health.duckdb"
REPO_ID  = "aiq00479/health-storage"

PAGES = [
    "💬 Agent Chat",
    "📊 Health Risk Dashboard",
    "📄 EHR Summarizer",
    "🩻 MediSync Imaging",
    "📰 Health News",
    "🛡️ Compliance",
]

# ---------------------------------------------------------------------------
# AGENT SYSTEM PROMPT  (shared base)
# ---------------------------------------------------------------------------
HEALTH_SYSTEM_PROMPT = """You are the Health Digital Workforce AI — a team of five
specialist agents (NOVA, AXIOM, NEXUS, PROMETHEUS, SENTINEL) managing population
health monitoring and chronic disease prevention for Australian health services.

Answer questions about: patient health risk, BMI disease thresholds, blood pressure
staging, diabetes risk from glucose/HbA1c, chronic disease prevention, clinical ML
models, population health reporting, EHR summarization, and medical imaging findings.

Be concise, clinical, and practical. Use Australian health context where relevant
(My Health Record, PBS, MBS, state health services).

Key thresholds:
- BMI: <18.5 Underweight | 18.5-24.9 Normal | 25-29.9 Overweight | 30-34.9 Obese I | 35-39.9 Obese II | ≥40 Obese III
- BP: <120/80 Normal | 120-129 Elevated | 130-139 Stage 1 HTN | ≥140 Stage 2 HTN | ≥180 Crisis
- Glucose: <5.6 Normal | 5.6-6.9 Pre-diabetic | ≥7.0 Diabetic
- HbA1c: <5.7% Normal | 5.7-6.4% Pre-diabetic | ≥6.5% Diabetic"""
