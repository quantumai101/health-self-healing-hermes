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
GEMINI_BASE_URL      = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MAX_TOKENS    = 2048
GEMINI_TEMPERATURE   = 0.4
GEMINI_RETRY_ATTEMPTS= 2
GEMINI_RETRY_CODES   = {429, 503, 502, 504}

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
    "Underweight": (0,               BMI_UNDERWEIGHT),
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
BP_NORMAL   = 120
BP_ELEVATED = 130
BP_STAGE1   = 140
BP_CRISIS   = 180

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
UI_BG           = "#060b18"
UI_SIDEBAR_BG   = "#0a1120"
UI_ACCENT       = "#38bdf8"
UI_USER_MSG_BG  = "#1a2f55"
UI_AGENT_MSG_BG = "#0f172a"
UI_FONT_MONO    = "JetBrains Mono"
UI_FONT_DISPLAY = "Share Tech Mono"

# ---------------------------------------------------------------------------
# GLOBAL CSS
# Injected once at startup via st.markdown(UI_CSS, unsafe_allow_html=True).
#
# Original rules from AGENTS.md Section 8 are fully preserved.
# Added on top:
#   • Space Mono import for sidebar nav buttons
#   • .health-topbar-title  — page header used in each pages/*.py render()
#   • Active-tab highlighted frame (raw HTML rendered in app.py)
#   • st.status "Thinking" block font override
#   • Suggestion chip button styles (main content area only)
# ---------------------------------------------------------------------------
UI_CSS = """
<style>
/* ── Fonts ──────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono&family=Share+Tech+Mono&family=Space+Mono:wght@400;700&display=swap');

/* ── Global base (original) ─────────────────────────────────────────────── */
html, body, [class*="css"] { font-family: 'JetBrains Mono', monospace !important; }
h1, h2, h3, h4 {
    font-family: 'Share Tech Mono', sans-serif !important;
    color: #38bdf8 !important;
    text-transform: uppercase;
}
.stApp { background: #060b18; }
[data-testid="stSidebar"] {
    background: #0a1120 !important;
    border-right: 1px solid #1e293b;
}

/* ── Original chat bubble classes (used by pages that call st.markdown) ──── */
.user-msg {
    background: #1a2f55;
    border-radius: 10px;
    padding: 12px;
    margin: 6px 0;
    border: 1px solid #3b82f6;
    color: #e2e8f0;
}
.agent-msg {
    background: #0f172a;
    border-left: 4px solid #38bdf8;
    padding: 12px;
    margin: 6px 0;
    color: #cbd5e1;
}
.disclaimer {
    background: #1a1a2e;
    border: 1px solid #f59e0b;
    border-radius: 8px;
    padding: 10px;
    color: #f59e0b;
    font-size: 0.85rem;
    margin: 8px 0;
}

/* ── Streamlit native st.chat_message bubbles ────────────────────────────── */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: rgba(59, 130, 246, 0.08);
    border: 1px solid rgba(59, 130, 246, 0.25);
    border-radius: 10px 10px 2px 10px;
}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: rgba(56, 189, 248, 0.04);
    border: 1px solid rgba(56, 189, 248, 0.10);
    border-radius: 2px 10px 10px 10px;
}

/* ── Sidebar nav buttons — Space Mono, rectangular, accent on hover ───────── */
section[data-testid="stSidebar"] .stButton > button {
    font-family: 'Space Mono', monospace !important;
    font-size: 11px !important;
    letter-spacing: 0.04em;
    border-radius: 6px;
    border: 1px solid rgba(255,255,255,0.08);
    background: transparent;
    color: #7070a0;
    padding: 7px 10px;
    text-align: left;
    transition: background 0.15s, color 0.15s, border-color 0.15s;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.04);
    color: #c8c4e0;
    border-color: rgba(255,255,255,0.15);
}

/* Remove extra bottom margin from the raw-HTML active-tab frames */
section[data-testid="stSidebar"] p { margin-bottom: 0 !important; }

/* ── Page topbar title class (used in each pages/*.py render()) ───────────── */
.health-topbar-title {
    font-family: 'Space Mono', monospace;
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.08em;
}

/* ── st.status "Thinking and reasoning..." block ─────────────────────────── */
.stStatusWidget {
    font-family: 'Space Mono', monospace !important;
    font-size: 11px !important;
    border-radius: 8px;
}

/* ── Suggestion chip buttons (main content area only) ────────────────────── */
.main .stButton > button {
    font-family: 'Space Mono', monospace;
    font-size: 10px;
    letter-spacing: 0.03em;
    border: 1px solid rgba(245, 200, 66, 0.25);
    background: rgba(245, 200, 66, 0.04);
    color: #c0b870;
    border-radius: 6px;
    padding: 8px 12px;
    text-align: left;
    white-space: normal;
    height: auto;
    line-height: 1.5;
    transition: background 0.15s, border-color 0.15s;
}
.main .stButton > button:hover {
    background: rgba(245, 200, 66, 0.09);
    border-color: rgba(245, 200, 66, 0.5);
    color: #e0d890;
}

/* ── Misc layout tweaks ──────────────────────────────────────────────────── */
section[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
.block-container { padding-top: 1.5rem; }
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
