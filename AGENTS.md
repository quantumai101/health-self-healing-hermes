# AGENTS.md — The Harness Manifesto
## `health-self-healing-hermes`
### A Population Health AI Platform · Inspired by Medivance.AI

> **This document is the single source of truth for all agents building this project.**
> Any logic, feature, or module NOT defined here does not exist.
> No agent may deviate from these contracts without human approval and a plan update.

---

## 1. PROJECT IDENTITY & MISSION

```
Project Name : health-self-healing-hermes
Platform     : Streamlit (HuggingFace Spaces deployment)
AI Backend   : Google Gemini 3 Flash (primary) → 3.1 Flash-Lite → 2.5 Flash (fallback chain)
Database     : DuckDB (local /tmp/) + HuggingFace Dataset repo backup
Language     : Python 3.11+
Style        : Dark cyberpunk clinical UI (JetBrains Mono + Share Tech Mono)
Target Users : Clinicians, health data analysts, population health managers
```

**Mission:** Build a production-grade, self-healing population health AI platform that matches
the feature depth of Medivance.AI (EHR summarization, medical imaging analysis, risk scoring,
compliance, virtual consultation workflow) — but deployed as a Streamlit HF Space with a
5-agent digital workforce architecture and Gemini 3 as the intelligence layer.

---

## 2. THE IRON RULES (Agents must never violate these)

| # | Rule | Consequence of Violation |
|---|------|--------------------------|
| 1 | **No hardcoded API keys** — all secrets via `os.environ` or `st.secrets` | BLOCK build |
| 2 | **Every agent function must have an offline fallback** — 503/429/timeout must never crash the UI | BLOCK build |
| 3 | **No single `app.py` monolith** — each agent lives in its own file under `agents/` | BLOCK merge |
| 4 | **Every new feature must have a plan file** in `plans/` before implementation begins | BLOCK merge |
| 5 | **Gemini calls always use the 3-model fallback chain** — never call a single model directly | BLOCK build |
| 6 | **All PHI/patient data is synthetic** — no real patient data ever enters the codebase | IMMEDIATE STOP |
| 7 | **All imports at top of file** — no inline imports except for optional heavy deps | WARN |
| 8 | **Test coverage ≥ 80%** for every agent module | BLOCK merge |

---

## 3. REPOSITORY STRUCTURE (The Law)

```
health-self-healing-hermes/
│
├── AGENTS.md                    ← THIS FILE (do not modify without human approval)
├── app.py                       ← Entry point ONLY — imports pages, sets config
├── requirements.txt
├── .env.example                 ← Template only, never commit .env
│
├── agents/                      ← One file per agent, no exceptions
│   ├── __init__.py
│   ├── nova.py                  ← Data ingestion & EHR quality
│   ├── axiom.py                 ← ML risk modelling & disease prediction
│   ├── nexus.py                 ← Digital twin & population simulation
│   ├── prometheus.py            ← Reporting, analytics & health news
│   └── sentinel.py             ← Compliance, security & audit
│
├── core/                        ← Shared infrastructure, imported by agents
│   ├── __init__.py
│   ├── gemini.py               ← Gemini fallback chain (THE ONLY place Gemini is called)
│   ├── config.py               ← All constants, thresholds, model IDs
│   ├── db.py                   ← DuckDB connection & schema management
│   └── session.py              ← Streamlit session state helpers
│
├── pages/                       ← Streamlit page modules
│   ├── __init__.py
│   ├── chat.py                 ← Agent Chat page
│   ├── dashboard.py            ← Health Risk Dashboard
│   ├── ehr_summarizer.py       ← EHR / Medical Record Summarization (NEW)
│   ├── imaging.py              ← Medical Imaging Analysis — MediSync (NEW)
│   ├── consultation.py         ← Virtual Consultation Workflow (NEW)
│   ├── news.py                 ← AI-Curated Health News Feed (NEW)
│   └── compliance.py           ← HIPAA Compliance & Audit page (NEW)
│
├── tools/                       ← Stateless utility functions
│   ├── __init__.py
│   ├── bmi_calculator.py
│   ├── bp_classifier.py
│   ├── glucose_classifier.py
│   ├── risk_scorer.py
│   ├── pdf_extractor.py        ← For EHR document upload
│   └── image_analyzer.py       ← For medical image processing
│
├── data/                        ← Synthetic datasets only
│   ├── synthetic_patients.py   ← Generator, not static CSV
│   └── medical_kb.py           ← Clinical knowledge base (thresholds, drug refs)
│
├── plans/                       ← Blueprint files (REQUIRED before implementation)
│   ├── ehr_module_v1.md
│   ├── imaging_module_v1.md
│   ├── consultation_module_v1.md
│   ├── news_module_v1.md
│   └── compliance_module_v1.md
│
├── tests/                       ← pytest tests, mirror structure of agents/ and tools/
│   ├── test_nova.py
│   ├── test_axiom.py
│   ├── test_gemini_fallback.py
│   ├── test_bmi_calculator.py
│   └── test_risk_scorer.py
│
└── docs/                        ← Feature documentation
    ├── architecture.md
    ├── clinical_thresholds.md
    └── deployment.md
```

---

## 4. THE FIVE AGENTS — Contracts & Responsibilities

### 🌟 NOVA — Data Ingestion & EHR Quality
```
File        : agents/nova.py
Class       : NovaAgent
Trigger     : "Ingest synthetic patient biometric data and run clinical quality checks"
              "Upload and summarize EHR document"
              "Validate patient record completeness"

Responsibilities:
  - Ingest synthetic patient biometric records (BMI, BP, glucose, HbA1c, age)
  - Run clinical quality checks (completeness %, out-of-range flags)
  - Accept PDF/text EHR uploads and extract structured data
  - Write validated records to DuckDB patient_health_records table
  - Generate data quality report with flag summary

Offline Fallback: Must return simulated ingestion result (1,240 records, 98.2% quality)
Gemini Role: Summarize extracted EHR text into structured clinical format
```

### 🧠 AXIOM — ML Risk Modelling & Disease Prediction
```
File        : agents/axiom.py
Class       : AxiomAgent
Trigger     : "Train the XGBoost chronic disease risk model"
              "Predict chronic disease risk for patient with BMI X, BP Y, glucose Z"
              "Analyse imaging results for pathology"

Responsibilities:
  - Train XGBoost model on synthetic patient cohort
  - Return AUC, sensitivity, specificity, top features
  - Accept individual patient biometrics → return risk score + clinical explanation
  - Integrate with MediSync imaging tool for X-ray/scan analysis
  - Provide HbA1c → diabetes risk mapping

Offline Fallback: Must return AUC 0.934, top features, simulated risk score
Gemini Role: Generate clinical explanation of risk score in plain language
```

### 🔗 NEXUS — Digital Twin & Population Simulation
```
File        : agents/nexus.py
Class       : NexusAgent
Trigger     : "Run population health digital twin simulation"
              "Simulate intervention impact on cohort"
              "Identify disease clusters in population"

Responsibilities:
  - Run population-level simulation on patient cohort from DuckDB
  - Detect disease clusters (T2DM + hypertension + obesity comorbidity)
  - Model intervention scenarios (weight loss programme → CVD risk reduction)
  - Generate cohort trajectory over 5-year horizon

Offline Fallback: 1,240 patient cohort, 247 obese, 3 critical clusters
Gemini Role: Interpret simulation results and recommend population interventions
```

### 📊 PROMETHEUS — Reporting, Analytics & Health News
```
File        : agents/prometheus.py
Class       : PrometheusAgent
Trigger     : "Generate executive weekly population health report"
              "Show AI-curated health news"
              "Analyse sentiment of clinical notes"

Responsibilities:
  - Generate weekly population health report (PDF-downloadable)
  - Curate and summarize latest health/medical news via Gemini web context
  - Perform sentiment & entity analysis on clinical narrative text
  - Produce trend charts (week-over-week risk deltas)

Offline Fallback: Week 11 2026 report, 1,240 patients, 247 high-risk
Gemini Role: Write executive report narrative + news summaries + sentiment analysis
```

### 🛡️ SENTINEL — Compliance, Security & Audit
```
File        : agents/sentinel.py
Class       : SentinelAgent
Trigger     : "Run health data compliance scan"
              "Rotate the API secret"
              "Audit PHI handling policy"

Responsibilities:
  - Evaluate 142 HIPAA / My Health Record (Australia) compliance rules
  - Scan codebase for PHI exposure risks (synthetic data only flag)
  - Rotate API secrets via environment variable update log
  - Generate compliance certificate with timestamp

Offline Fallback: 142 rules evaluated, 2 minor exceptions, green status
Gemini Role: Generate compliance report narrative and remediation recommendations
```

---

## 5. THE GEMINI CALL CONTRACT (core/gemini.py)

**This is the ONLY file that may call the Gemini API. All agents import from here.**

```python
# Contract: gemini_chat(prompt, system_prompt=HEALTH_SYSTEM_PROMPT) -> str
# - Tries gemini-3-flash-preview first
# - Falls back to gemini-3.1-flash-lite-preview on 429/503/502/504
# - Falls back to gemini-2.5-flash on continued failure
# - Returns offline fallback string on total failure — NEVER raises exception to UI
# - Logs each attempt via add_log()
# - maxOutputTokens: 2048
# - temperature: 0.4

GEMINI_MODELS = [
    ("gemini-3-flash-preview",       "Gemini 3 Flash"),
    ("gemini-3.1-flash-lite-preview","Gemini 3.1 Flash-Lite"),
    ("gemini-2.5-flash",             "Gemini 2.5 Flash"),
]
```

---

## 6. FEATURES — Full Feature Matrix

### Inherited from existing health-hermes (KEEP & IMPROVE)
| Feature | Page | Agent |
|---------|------|-------|
| Agent Chat (5 agents) | `pages/chat.py` | All agents |
| Patient Health Risk Dashboard | `pages/dashboard.py` | AXIOM + NOVA |
| BMI Band Distribution & Disease Risk Mapping | `pages/dashboard.py` | AXIOM |
| BMI vs Risk Score Bubble Chart | `pages/dashboard.py` | AXIOM |
| Blood Pressure Stage Distribution | `pages/dashboard.py` | AXIOM |
| Fasting Glucose / Diabetes Risk Pie | `pages/dashboard.py` | AXIOM |
| High-Risk Patient Table | `pages/dashboard.py` | NOVA |
| DuckDB persistence + HF backup/sync | `core/db.py` | NOVA |
| Offline fallback responses | `core/gemini.py` | All |
| Gemini 3-model fallback chain | `core/gemini.py` | All |

### NEW — Inspired by Medivance.AI (BUILD THESE)
| Feature | Page | Agent | Priority |
|---------|------|-------|----------|
| **EHR Summarization** — Upload PDF medical records → AI structured summary | `pages/ehr_summarizer.py` | NOVA + Gemini | 🔴 P1 |
| **MediSync Imaging** — Upload X-ray/scan image → AI diagnostic report | `pages/imaging.py` | AXIOM + Gemini | 🔴 P1 |
| **Virtual Consultation Workflow** — Schedule, validate, complete appointments | `pages/consultation.py` | PROMETHEUS | 🟡 P2 |
| **AI Health News Feed** — Gemini-curated medical news with sentiment | `pages/news.py` | PROMETHEUS | 🟡 P2 |
| **Sentiment & Entity Analysis** — Clinical narrative NLP | `pages/chat.py` | PROMETHEUS | 🟡 P2 |
| **Compliance Dashboard** — HIPAA/My Health Record audit view | `pages/compliance.py` | SENTINEL | 🟢 P3 |
| **Doctor Verification Panel** — Simulated credentialing workflow | `pages/consultation.py` | SENTINEL | 🟢 P3 |
| **Downloadable PDF Reports** — Weekly health reports as PDF | `pages/dashboard.py` | PROMETHEUS | 🟡 P2 |
| **Population Intervention Simulator** — Model intervention outcomes | `pages/dashboard.py` | NEXUS | 🟡 P2 |

---

## 7. CLINICAL KNOWLEDGE BASE (The Single Source of Truth for Thresholds)

All agents must import thresholds from `data/medical_kb.py`. No agent may hardcode these.

```python
# BMI
BMI_UNDERWEIGHT  = 18.5
BMI_NORMAL_MAX   = 24.9
BMI_OVERWEIGHT   = 25.0
BMI_OBESE_I      = 30.0
BMI_OBESE_II     = 35.0
BMI_OBESE_III    = 40.0

# Blood Pressure (systolic mmHg)
BP_NORMAL        = 120
BP_ELEVATED      = 130
BP_STAGE1_HTN    = 140
BP_STAGE2_HTN    = 180   # crisis above this

# Fasting Glucose (mmol/L)
GLUCOSE_NORMAL      = 5.6
GLUCOSE_PREDIABETIC = 7.0

# HbA1c (%)
HBA1C_NORMAL      = 5.7
HBA1C_PREDIABETIC = 6.5

# Risk Score Bands
RISK_LOW      = 0.30
RISK_MODERATE = 0.60
RISK_HIGH     = 0.80
```

---

## 8. UI CONTRACT (The Visual Standard)

All pages must use these CSS variables. No page may introduce its own colour scheme.

```css
Background    : #060b18  (near-black dark blue)
Sidebar       : #0a1120
User message  : #1a2f55 (border: #3b82f6)
Agent message : #0f172a (left-border: #38bdf8)
Accent        : #38bdf8  (sky blue)
Critical      : #ef4444  (red)
Warning       : #f59e0b  (amber)
OK            : #22c55e  (green)
Font Mono     : JetBrains Mono
Font Display  : Share Tech Mono
Headings      : uppercase, #38bdf8
```

---

## 9. DATA CONTRACT (Synthetic Only)

The `data/synthetic_patients.py` generator must produce:

```python
REQUIRED_COLUMNS = [
    "patient_id",          # PAT-XXXX
    "age_years",           # 25–75
    "bmi",                 # 15.0–55.0 (realistic distribution)
    "bmi_band",            # Underweight/Normal/Overweight/Obese I/II/III
    "systolic_bp",         # 105–185
    "fasting_glucose_mmol",# 3.5–9.5
    "hba1c_pct",           # 4.5–10.0  ← NEW
    "risk_score",          # 0.05–0.98
    "status",              # OK/REVIEW/CRITICAL
    "disease_risk",        # text description
    "region",              # Australian states/territories  ← NEW
    "in_high_risk_zone",   # Yes/No
    "patients_affected",   # 1–10
    "last_review_date",    # date string  ← NEW
]
```

---

## 10. DEPLOYMENT CONTRACT

```yaml
# HuggingFace Space settings
SDK       : streamlit
Python    : 3.11
Hardware  : CPU basic (free tier)

# Required Space Secrets (never in code)
GEMINI_API_KEY       : Google AI Studio key
HF_TOKEN             : HuggingFace read/write token

# Entry point
app_file  : app.py

# requirements.txt must include (minimum):
streamlit>=1.35
plotly>=5.20
pandas>=2.0
numpy>=1.26
duckdb>=0.10
huggingface_hub>=0.22
google-genai>=0.8
python-dotenv>=1.0
Pillow>=10.0         # for imaging page
PyPDF2>=3.0          # for EHR PDF upload
pytest>=8.0          # for test suite
```

---

## 11. PHASE BUILD ORDER (The Harness Sequence)

Agents build in this order. Each phase requires human sign-off before the next begins.

```
PHASE 1 ✅  MANIFESTO          — This document (AGENTS.md)
PHASE 2     CORE SCAFFOLD      — app.py shell + core/ + data/ + config
PHASE 3     AGENT STUBS        — All 5 agents with offline fallbacks only (no Gemini yet)
PHASE 4     GEMINI CORE        — core/gemini.py fallback chain + test_gemini_fallback.py
PHASE 5     EXISTING PAGES     — chat.py + dashboard.py (port from current app.py)
PHASE 6     EHR SUMMARIZER     — pages/ehr_summarizer.py (P1 new feature)
PHASE 7     MEDISYNC IMAGING   — pages/imaging.py (P1 new feature)
PHASE 8     CONSULTATION       — pages/consultation.py + news.py (P2)
PHASE 9     COMPLIANCE         — pages/compliance.py (P3)
PHASE 10    AUDIT & HARDEN     — Sentinel audit pass, test coverage check, deploy
```

---

## 12. AGENT PROMPTS (The Exact Prompts for Each Build Phase)

These are the prompts a human gives to an AI coding agent (Claude Code, Cursor, etc.)
at each phase. Copy-paste exactly.

### Phase 2 Prompt — Core Scaffold
```
You are a Feature Agent building health-self-healing-hermes.
Read AGENTS.md completely before writing any code.
Create the following files with correct content matching the contracts in AGENTS.md:
  - app.py (entry point only, imports pages, sets st.set_page_config)
  - core/config.py (all constants from section 7 and 8)
  - core/gemini.py (Gemini fallback chain from section 5, no other logic)
  - core/db.py (DuckDB connect, schema creation for patient_health_records)
  - core/session.py (add_log, session state init helpers)
  - data/medical_kb.py (all thresholds from section 7)
  - data/synthetic_patients.py (generator producing all columns in section 9)
  - requirements.txt (all packages from section 10)
Do not implement any page or agent yet. Run: python -c "import app" to verify no import errors.
```

### Phase 3 Prompt — Agent Stubs
```
You are a Feature Agent. Read AGENTS.md section 4.
Create agents/nova.py, agents/axiom.py, agents/nexus.py, agents/prometheus.py, agents/sentinel.py.
Each agent must:
  1. Be a class (NovaAgent, AxiomAgent, etc.)
  2. Have a run(command: str) -> str method
  3. Return the correct offline fallback string for each trigger command (from section 4)
  4. NOT call Gemini yet — offline only
  5. Have a corresponding test in tests/test_{agentname}.py that asserts offline fallbacks return non-empty strings
Run pytest tests/ and confirm all pass before finishing.
```

### Phase 4 Prompt — Gemini Core
```
You are a Feature Agent. Read AGENTS.md section 5.
Implement core/gemini.py with:
  - gemini_chat(prompt, system_prompt, offline_fallback) -> str
  - 3-model fallback chain: gemini-3-flash-preview → gemini-3.1-flash-lite-preview → gemini-2.5-flash
  - Retry logic: 2 attempts per model with exponential backoff on 429/503/502/504
  - Returns offline_fallback string (never raises) on total failure
  - Logs each attempt via add_log() from core/session.py
  - Stores active model name in st.session_state["active_gemini_model"]
Create tests/test_gemini_fallback.py that mocks requests.post to return 503 for all models
and asserts that gemini_chat returns the offline_fallback string without raising.
Run pytest tests/test_gemini_fallback.py and confirm it passes.
```

### Phase 6 Prompt — EHR Summarizer (P1 Feature)
```
You are a Feature Agent. Read AGENTS.md sections 4 (NOVA) and 6 (EHR Summarization row).
Read plans/ehr_module_v1.md before writing code.
Implement pages/ehr_summarizer.py as a Streamlit page with:
  1. File uploader accepting PDF and TXT medical records
  2. PDF text extraction using PyPDF2 (tool: tools/pdf_extractor.py)
  3. Call core/gemini.py gemini_chat() with the extracted text and NOVA system prompt
  4. Display structured AI summary: Chief Complaint, Diagnosis, Medications, 
     Lab Results, Risk Flags, Recommended Actions
  5. Show a "Download Summary" button that exports the summary as a text file
  6. Full offline fallback if Gemini unavailable (show example summary)
  7. Follow UI contract from AGENTS.md section 8 exactly
Run the page locally with: streamlit run app.py and confirm no errors before finishing.
```

### Phase 7 Prompt — MediSync Imaging (P1 Feature)
```
You are a Feature Agent. Read AGENTS.md sections 4 (AXIOM) and 6 (MediSync Imaging row).
Read plans/imaging_module_v1.md before writing code.
Implement pages/imaging.py as a Streamlit page with:
  1. Image uploader accepting PNG, JPG, DICOM-as-PNG medical images
  2. Display uploaded image with Pillow (tools/image_analyzer.py)
  3. Extract basic image metadata (size, mode, histogram analysis)
  4. Send image description + metadata to gemini_chat() with AXIOM imaging system prompt
  5. Display AI diagnostic report: Findings, Anomaly Flags, Confidence Level, 
     Recommended Follow-up
  6. Disclaimer: "This is a simulation. Not for clinical use."
  7. Full offline fallback with example chest X-ray report
  8. Follow UI contract from AGENTS.md section 8 exactly
Note: Use Gemini text-based analysis of image metadata only (not vision API) 
unless GEMINI_VISION=true is set in environment.
```

---

## 13. SELF-HEALING CONTRACT

The platform must self-heal on the following failure modes without human intervention:

| Failure | Self-Healing Behaviour |
|---------|----------------------|
| Gemini 503/429 | Auto-fallback to next model in chain |
| All Gemini models fail | Show offline simulation response |
| DuckDB file missing | Recreate schema + load synthetic data |
| HF sync fails | Log error, continue with local DB |
| PDF extraction fails | Show "Could not parse PDF" + manual text input field |
| Image upload fails | Show example analysis with disclaimer |
| Missing API key | Show setup instructions in sidebar, not crash |

---

*AGENTS.md version 1.0 — Approved for Phase 2 build commencement.*
*Last updated: April 2026*
*Human sign-off required before modifying Iron Rules (Section 2) or Feature Matrix (Section 6).*
