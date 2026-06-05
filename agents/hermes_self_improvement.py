"""
agents/hermes_self_improvement.py
==================================
HERMES Autonomous Self-Improvement Agent
Inspired by RecursiveMAS — runs while you sleep.

What it does every cycle (default: every 2 hours):
  1. AUDIT    — scans all agents/*.py and pages/*.py for known issues
  2. CRITIQUE — Gemini reviews each file and scores it (0-10)
  3. IMPROVE  — Gemini rewrites low-scoring files (score < 7)
  4. VALIDATE — runs basic syntax check on the rewrite
  5. COMMIT   — saves improved file + writes a change-log entry
  6. REPORT   — appends a markdown summary to self_improvement_log.md

Run once manually:
    python agents/hermes_self_improvement.py --once

Run as a background daemon (keep terminal open or use nohup):
    python agents/hermes_self_improvement.py --daemon

RecursiveMAS concepts adopted:
  • Inner loop  = per-file critique → rewrite → validate
  • Outer loop  = cross-file consistency check (imports, shared state)
  • HF resolver = optional: pull improved agent templates from HuggingFace
                  (set HF_AGENT_REPO in .env to enable)

Requirements:
    pip install google-genai schedule
"""

import os
import sys
import ast
import time
import shutil
import argparse
import textwrap
import schedule
from pathlib import Path
from datetime import datetime

# ── .env loader ───────────────────────────────────────────────────────────────
def load_dotenv():
    for base in [Path.cwd()] + list(Path.cwd().parents)[:2]:
        env = base / ".env"
        if env.exists():
            with open(env, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip(); v = v.strip().strip('"').strip("'")
                    if k not in os.environ:
                        os.environ[k] = v
            return

load_dotenv()

# ── Gemini SDK ────────────────────────────────────────────────────────────────
try:
    from google import genai
    from google.genai import types as gtypes
except ImportError:
    sys.exit("❌  pip install google-genai")

# ── Optional HuggingFace resolver (RecursiveMAS hf_resolver.py concept) ──────
HF_AGENT_REPO = os.getenv("HF_AGENT_REPO", "").strip()
try:
    from huggingface_hub import snapshot_download
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

# ── Config ────────────────────────────────────────────────────────────────────
MODELS           = ["gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash"]
SCORE_THRESHOLD  = 7          # files scoring below this get rewritten
CYCLE_HOURS      = 2          # how often the daemon runs
MAX_FILE_CHARS   = 20_000     # increased: prevents truncation of large files
LOG_FILE         = "self_improvement_log.md"
BACKUP_SUFFIX    = ".bak"

# ── Files to audit (relative to project root) ─────────────────────────────────
AUDIT_TARGETS = [
    "agents/clinical_ensemble_orchestrator_v2.py",
    "agents/psa_clinical_orchestrator_v3.py",
    "pages/imaging.py",
    "pages/dashboard.py",
    "pages/chat.py",
    "auth/session.py",
]

# ── Protected files — critiqued but NEVER auto-rewritten ─────────────────────
# Add files with patient-specific UI or hand-crafted logic that must not
# be overwritten by the AI agent even if they score below threshold.
PROTECTED_FILES = [
    "pages/dashboard.py",    # contains CTCA simulation button (ZHANG, ZHIMING)
]

# ── Gemini client ─────────────────────────────────────────────────────────────
def get_client():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        sys.exit("❌  GEMINI_API_KEY not set in .env")
    return genai.Client(api_key=api_key)


def call_gemini(client, prompt: str, max_tokens: int = 3000) -> str:
    """Call Gemini with model fallback chain."""
    for model in MODELS:
        for attempt in range(3):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=gtypes.GenerateContentConfig(
                        temperature=0.1,
                        max_output_tokens=max_tokens,
                    )
                )
                return resp.text
            except Exception as e:
                err = str(e)
                if "429" in err or "quota" in err.lower():
                    wait = 30 * (attempt + 1)
                    print(f"   ⏳ Rate limit — waiting {wait}s ...")
                    time.sleep(wait)
                elif "404" in err:
                    break
                else:
                    print(f"   ⚠️  {model}: {err[:80]}")
                    break
    return ""


# ── STEP 1: AUDIT — read file, truncate if needed ────────────────────────────
def audit_file(path: Path) -> str | None:
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8", errors="replace")
    if len(content) > MAX_FILE_CHARS:
        content = content[:MAX_FILE_CHARS] + "\n\n# ... [TRUNCATED FOR REVIEW] ..."
    return content


# ── STEP 2: CRITIQUE — Gemini scores the file ─────────────────────────────────
CRITIQUE_PROMPT = """You are a senior Python engineer reviewing medical AI application code.

Review this file from the HERMES health AI platform:

FILE: {filename}
```python
{code}
```

Score the file on a scale of 0–10 for EACH of:
1. Code quality (readability, structure, docstrings)
2. Error handling (try/except, validation, graceful degradation)
3. Security (no hardcoded secrets, safe file handling)
4. Clinical safety (appropriate disclaimers, no false certainty)
5. Performance (no blocking calls, efficient data handling)

Respond ONLY in this exact JSON format — no markdown, no explanation:
{{
  "scores": {{
    "code_quality": <int>,
    "error_handling": <int>,
    "security": <int>,
    "clinical_safety": <int>,
    "performance": <int>
  }},
  "overall": <int 0-10>,
  "top_issues": ["issue 1", "issue 2", "issue 3"],
  "quick_wins": ["fix 1", "fix 2"]
}}"""


def critique_file(client, filename: str, code: str) -> dict:
    prompt = CRITIQUE_PROMPT.format(filename=filename, code=code)
    raw = call_gemini(client, prompt, max_tokens=800)
    # Strip markdown fences if present
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return __import__("json").loads(raw)
    except Exception:
        return {"overall": 8, "top_issues": [], "quick_wins": [],
                "scores": {}, "_parse_error": raw[:200]}


# ── STEP 3: IMPROVE — Gemini rewrites the file ────────────────────────────────
IMPROVE_PROMPT = """You are a senior Python engineer improving medical AI application code.

The file below scored {score}/10. Known issues:
{issues}

Quick wins to apply:
{wins}

FILE: {filename}
```python
{code}
```

Rewrite the COMPLETE file fixing the issues above.
Rules:
- Keep ALL existing functionality — do NOT remove features
- Add/improve docstrings and inline comments
- Add proper try/except where missing
- Never add hardcoded API keys or passwords
- For clinical code: add appropriate uncertainty disclaimers in comments
- Return ONLY the raw Python code, no markdown fences, no explanation

IMPORTANT: The output must be valid Python that passes ast.parse()."""


def improve_file(client, filename: str, code: str, critique: dict) -> str:
    issues = "\n".join(f"- {i}" for i in critique.get("top_issues", []))
    wins   = "\n".join(f"- {w}" for w in critique.get("quick_wins", []))
    score  = critique.get("overall", 0)
    prompt = IMPROVE_PROMPT.format(
        filename=filename, code=code,
        score=score, issues=issues or "- General quality improvement",
        wins=wins or "- Improve readability"
    )
    return call_gemini(client, prompt, max_tokens=4000)


# ── STEP 4: VALIDATE — syntax check ──────────────────────────────────────────
def validate_python(code: str) -> tuple[bool, str]:
    # Strip markdown fences Gemini sometimes adds despite instructions
    code = code.strip()
    if code.startswith("```"):
        lines = code.split("\n")
        code  = "\n".join(lines[1:])
    if code.endswith("```"):
        code = code.rsplit("```", 1)[0]
    code = code.strip()
    try:
        ast.parse(code)
        return True, code
    except SyntaxError as e:
        return False, str(e)


# ── STEP 5: COMMIT — backup + save (Windows-safe) ────────────────────────────
def commit_improvement(path: Path, new_code: str) -> bool:
    """
    Windows-safe backup and save.
    Uses shutil.copy2 + unlink instead of rename() to avoid
    WinError 183 (cannot rename over an existing file).
    Backup name includes timestamp so repeated cycles never collide.
    """
    ts     = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_suffix(f".{ts}.bak")
    try:
        # Step 1 — copy original to timestamped backup (never overwrites)
        shutil.copy2(path, backup)

        # Step 2 — write improved version over the original
        path.write_text(new_code, encoding="utf-8")

        print(f"   ✅ Saved : {path.name}")
        print(f"   📦 Backup: {backup.name}")
        return True

    except Exception as e:
        print(f"   ❌ Save failed: {e}")
        # Restore from backup if we have one
        if backup.exists() and not path.exists():
            shutil.copy2(backup, path)
        return False


# ── STEP 6: REPORT — append to markdown log ──────────────────────────────────
def write_log_entry(results: list[dict]):
    now     = datetime.now().strftime("%Y-%m-%d %H:%M")
    log_path= Path(LOG_FILE)
    lines   = [f"\n## 🔁 Self-Improvement Cycle — {now}\n"]

    for r in results:
        status = "✅ IMPROVED" if r.get("improved") else (
                 "⏭ SKIPPED"  if r.get("skipped")  else "❌ FAILED")
        lines.append(f"### {r['file']} — {status}")
        lines.append(f"- Score: **{r.get('score','?')}/10**")
        if r.get("issues"):
            lines.append("- Issues fixed:")
            for issue in r["issues"]:
                lines.append(f"  - {issue}")
        lines.append("")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"📋  Log updated: {log_path}")


# ── Optional: pull improved templates from HuggingFace (RecursiveMAS concept) ─
def pull_hf_agent_templates() -> Path | None:
    """
    RecursiveMAS outer-loop concept: pull the latest agent templates
    from a HuggingFace model repo (set HF_AGENT_REPO in .env).
    These act as the 'outer adapter' — best-practice templates that
    guide the inner rewrite loop.
    """
    if not HF_AVAILABLE or not HF_AGENT_REPO:
        return None
    try:
        print(f"   📥 Pulling HF templates from: {HF_AGENT_REPO}")
        resolved = snapshot_download(repo_id=HF_AGENT_REPO, repo_type="model")
        return Path(resolved).resolve()
    except Exception as e:
        print(f"   ⚠️  HF pull failed: {e}")
        return None


# ── Main improvement cycle ────────────────────────────────────────────────────
def run_improvement_cycle():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n{'='*60}")
    print(f"🧠  HERMES SELF-IMPROVEMENT CYCLE  —  {now}")
    print(f"{'='*60}")

    client  = get_client()
    root    = Path.cwd()
    results = []

    # Optional HF outer-loop template pull
    hf_templates = pull_hf_agent_templates()
    if hf_templates:
        print(f"   ✅ HF templates available at: {hf_templates}")

    for rel_path in AUDIT_TARGETS:
        path = root / rel_path
        print(f"\n📄  Auditing: {rel_path}")

        # ── PROTECTED FILE CHECK ─────────────────────────────────────────────
        # Protected files are critiqued (for awareness) but never auto-rewritten
        is_protected = rel_path in PROTECTED_FILES

        # ── STEP 1: AUDIT ────────────────────────────────────────────────────
        code = audit_file(path)
        if code is None:
            print(f"   ⚠️  Not found — skipping")
            results.append({"file": rel_path, "skipped": True, "score": "N/A"})
            continue

        # ── STEP 2: CRITIQUE ─────────────────────────────────────────────────
        print(f"   🔍 Critiquing ...")
        critique = critique_file(client, rel_path, code)
        score    = critique.get("overall", 10)
        issues   = critique.get("top_issues", [])
        print(f"   📊 Score: {score}/10  |  Issues: {len(issues)}")
        for issue in issues[:3]:
            print(f"      • {issue}")

        if score >= SCORE_THRESHOLD:
            print(f"   ⏭  Score {score} ≥ {SCORE_THRESHOLD} — no rewrite needed")
            results.append({"file": rel_path, "skipped": True,
                            "score": score, "issues": issues})
            continue

        # ── PROTECTED: show issues but skip rewrite ───────────────────────────
        if is_protected:
            print(f"   🔒 PROTECTED — issues noted but rewrite blocked")
            print(f"      To manually fix, edit {rel_path} directly")
            results.append({"file": rel_path, "skipped": True,
                            "protected": True, "score": score, "issues": issues})
            continue

        # ── STEP 3: IMPROVE ──────────────────────────────────────────────────
        print(f"   ✏️  Score {score} < {SCORE_THRESHOLD} — requesting improvement ...")
        new_code = improve_file(client, rel_path, code, critique)

        if not new_code.strip():
            print(f"   ❌ Empty response — skipping")
            results.append({"file": rel_path, "improved": False,
                            "score": score, "issues": issues})
            continue

        # ── STEP 4: VALIDATE ─────────────────────────────────────────────────
        valid, result = validate_python(new_code)
        if not valid:
            print(f"   ❌ Syntax error in rewrite: {result[:80]}")
            results.append({"file": rel_path, "improved": False,
                            "score": score, "issues": issues})
            continue

        # ── STEP 5: COMMIT ───────────────────────────────────────────────────
        saved = commit_improvement(path, result)
        results.append({
            "file": rel_path, "improved": saved,
            "score": score, "issues": issues
        })

        # Rate limit courtesy pause
        time.sleep(5)

    # ── STEP 6: REPORT ───────────────────────────────────────────────────────
    write_log_entry(results)
    improved = sum(1 for r in results if r.get("improved"))
    print(f"\n🏁  Cycle complete — {improved}/{len(AUDIT_TARGETS)} files improved")
    print(f"{'='*60}\n")


# ── CLI entry point ───────────────────────────────────────────────────────────
def main():
    # global must be declared FIRST — before any reference to these names
    global CYCLE_HOURS, SCORE_THRESHOLD

    parser = argparse.ArgumentParser(
        description="HERMES Self-Improvement Agent (RecursiveMAS-inspired)"
    )
    parser.add_argument("--once",   action="store_true",
                        help="Run one cycle and exit")
    parser.add_argument("--daemon", action="store_true",
                        help="Run every N hours indefinitely")
    parser.add_argument("--hours",  type=float, default=CYCLE_HOURS,
                        help="Daemon cycle interval in hours (default: 2)")
    parser.add_argument("--threshold", type=int, default=SCORE_THRESHOLD,
                        help="Score threshold below which files are rewritten (default: 7)")
    args = parser.parse_args()

    CYCLE_HOURS     = args.hours
    SCORE_THRESHOLD = args.threshold

    if args.once or not args.daemon:
        run_improvement_cycle()
        return

    # ── Daemon mode ───────────────────────────────────────────────────────────
    print(f"🕐  Daemon started — cycle every {CYCLE_HOURS}h")
    print(f"    Score threshold: {SCORE_THRESHOLD}/10")
    print(f"    Watching {len(AUDIT_TARGETS)} files")
    print(f"    Log: {LOG_FILE}")
    print(f"    Press Ctrl+C to stop\n")

    run_improvement_cycle()   # run immediately on start
    schedule.every(CYCLE_HOURS).hours.do(run_improvement_cycle)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
