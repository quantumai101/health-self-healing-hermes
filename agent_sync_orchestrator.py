"""
agent_sync_orchestrator.py -- Self-Healing MFA & Persistence Agent
===================================================================
Multi-agent loop that patches auth.py, pushes to git, monitors HF space.
No CrewAI, no Ollama, no API keys required.

Run:
    python agent_sync_orchestrator.py
"""

import os
import io
import re
import sys
import time
import subprocess
import textwrap
from pathlib import Path

# Fix Windows stdout encoding (cp1252 -> utf-8)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import requests
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q"])
    import requests

# -- Configuration -------------------------------------------------------------

HF_SPACE_URL = "https://aiq00479-health-self-healing-hermes.hf.space/"
RESET_URL    = f"{HF_SPACE_URL}?reset_db=QUANTUM_RESET_2026"
AUTH_FILE    = Path("auth") / "auth.py"
LOG_FILE     = Path("agent_healer.log")

BANNER = """
+----------------------------------------------------------+
|  [HEALTH HERMES] Self-Healing Agent Workforce            |
|  Agent 1: Monitor | Agent 2: Surgeon | Agent 3: DevOps   |
+----------------------------------------------------------+
"""

# -- Shared log ----------------------------------------------------------------

def log(agent: str, msg: str):
    ts   = time.strftime("%H:%M:%S")
    line = f"[{ts}] [{agent}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ==============================================================================
# AGENT 1 -- MONITOR
# ==============================================================================

def agent_monitor() -> str:
    """
    Returns: HEALTHY | BUILD_ERROR | DB_WIPED | MFA_DRIFT | UNKNOWN
    """
    log("Monitor", f"Checking {HF_SPACE_URL} ...")
    try:
        r      = requests.get(HF_SPACE_URL, timeout=20)
        status = r.status_code
        body   = r.text

        if status >= 500:
            log("Monitor", f"[FAIL] HTTP {status} -- build/compile crash detected.")
            return "BUILD_ERROR"

        if "Invalid email or password" in body:
            log("Monitor", "[WARN] Login page reachable but credentials rejected -- DB likely wiped.")
            return "DB_WIPED"

        if "Sign in" in body or "Password" in body:
            log("Monitor", "[WARN] Login page reachable. Possible MFA drift.")
            return "MFA_DRIFT"

        if status == 200:
            log("Monitor", "[OK] Space appears HEALTHY.")
            return "HEALTHY"

        log("Monitor", f"[?] Unexpected HTTP {status}.")
        return "UNKNOWN"

    except requests.exceptions.ConnectionError:
        log("Monitor", "[FAIL] Cannot reach HF space -- network error or space sleeping.")
        return "BUILD_ERROR"
    except Exception as e:
        log("Monitor", f"[FAIL] Monitor error: {e}")
        return "UNKNOWN"

# ==============================================================================
# AGENT 2 -- SURGEON
# ==============================================================================

def agent_surgeon() -> dict:
    """
    Patches auth/auth.py:
      1. valid_window=1 -> valid_window=2  (fixes TOTP clock-drift rejection)
      2. Hardcoded DB_PATH -> /data routing (fixes DB wipe on HF rebuild)

    Returns {"ok": bool, "changes": [str]}
    """
    if not AUTH_FILE.exists():
        log("Surgeon", f"[FAIL] {AUTH_FILE} not found. Run from project root.")
        return {"ok": False, "changes": []}

    original = AUTH_FILE.read_text(encoding="utf-8")
    patched  = original
    changes  = []

    # -- Patch 1: TOTP valid_window -------------------------------------------
    if "valid_window=1" in patched:
        patched = patched.replace("valid_window=1", "valid_window=2")
        changes.append("TOTP valid_window raised 1->2 (fixes 30s clock-drift)")
        log("Surgeon", "[OK] Patched valid_window=1 -> valid_window=2")
    elif "valid_window=2" in patched:
        log("Surgeon", "[INFO] valid_window already at 2 -- no change needed.")
    else:
        log("Surgeon", "[WARN] valid_window not found -- check auth.py manually.")

    # -- Patch 2: DB_PATH persistent volume routing ---------------------------
    HF_MARKER = "HF Persistent Volume routing"

    if HF_MARKER not in patched:
        hf_block = (
            '# -- DB path -- HF Persistent Volume routing (patched by agent) --\n'
            '_DATA_DIR = Path("/data")\n'
            'DB_PATH   = (_DATA_DIR / "users.db") if _DATA_DIR.exists() '
            'else (Path(__file__).parent / "users.db")'
        )

        patterns = [
            r'DB_PATH\s*=\s*Path\(__file__\)\.parent\s*/\s*"users\.db"',
            r"DB_PATH\s*=\s*Path\(__file__\)\.parent\s*/\s*'users\.db'",
            r'DB_PATH\s*=.*users\.db.*',
        ]
        replaced = False
        for pat in patterns:
            if re.search(pat, patched):
                patched  = re.sub(pat, hf_block, patched)
                replaced = True
                log("Surgeon", f"[OK] DB_PATH routing injected (matched pattern).")
                break

        if not replaced:
            log("Surgeon", "[WARN] DB_PATH line not matched -- inserting after last import.")
            lines       = patched.splitlines()
            last_import = 0
            for i, line in enumerate(lines):
                if line.startswith(("import ", "from ")):
                    last_import = i
            lines.insert(last_import + 1, "\n" + hf_block)
            patched = "\n".join(lines)

        changes.append("DB_PATH now routes to /data/users.db on HF (survives rebuilds)")
    else:
        log("Surgeon", "[INFO] HF volume routing already present -- no change needed.")

    # -- Write file only if something changed ---------------------------------
    if patched != original:
        backup = AUTH_FILE.with_suffix(".py.bak_agent")
        backup.write_text(original, encoding="utf-8")
        log("Surgeon", f"[INFO] Backup saved: {backup}")
        AUTH_FILE.write_text(patched, encoding="utf-8")
        log("Surgeon", f"[OK] auth.py patched ({len(changes)} change(s)).")
    else:
        log("Surgeon", "[INFO] auth.py already optimal -- no file write needed.")

    return {"ok": True, "changes": changes}

# ==============================================================================
# AGENT 3 -- DEVOPS
# ==============================================================================

def _run(cmd: list, desc: str) -> bool:
    log("DevOps", f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    out    = result.stdout.strip()
    err    = result.stderr.strip()

    if result.returncode == 0:
        log("DevOps", f"[OK] {desc}")
        return True

    if "nothing to commit" in err or "nothing to commit" in out:
        log("DevOps", "[INFO] Nothing new to commit -- already up to date.")
        return True

    log("DevOps", f"[FAIL] {desc}: {err[:200]}")
    return False

def agent_devops(changes: list) -> bool:
    if not changes:
        log("DevOps", "[INFO] No code changes to push.")
        return True

    commit_msg = "fix(agent): " + "; ".join(changes[:2])

    _run(["git", "add", "auth/auth.py"], "Staged auth/auth.py")
    _run(["git", "commit", "-m", commit_msg], "Committed patch")

    hf_ok = _run(["git", "push", "huggingface", "main"], "Pushed -> huggingface/main")
    if not hf_ok:
        log("DevOps", "[WARN] HF push failed -- check 'git remote -v'.")

    gh_ok = _run(["git", "push", "origin", "main"], "Pushed -> origin/main")
    if not gh_ok:
        log("DevOps", "[WARN] GitHub push failed -- check remote auth.")

    return True

# ==============================================================================
# AGENT 4 -- RESET PULSE
# ==============================================================================

def agent_reset_pulse():
    log("ResetPulse", f"Firing DB reset: {RESET_URL}")
    try:
        r = requests.get(RESET_URL, timeout=15)
        log("ResetPulse", f"[OK] Reset signal sent -- HTTP {r.status_code}")
    except Exception as e:
        log("ResetPulse", f"[WARN] Reset pulse failed: {e}")

# ==============================================================================
# ORCHESTRATOR
# ==============================================================================

def main():
    print(BANNER)
    LOG_FILE.unlink(missing_ok=True)
    log("Orchestrator", "Starting self-healing loop...")

    # Phase 1: Surgeon patches auth.py
    log("Orchestrator", "--- Phase 1: Code Surgery ---")
    result = agent_surgeon()

    # Phase 2: DevOps commits and pushes
    log("Orchestrator", "--- Phase 2: Git Deployment ---")
    if result["changes"]:
        agent_devops(result["changes"])
        log("Orchestrator", "Waiting 90s for HF container rebuild...")
        for i in range(9):
            time.sleep(10)
            print(f"   ... {(i+1)*10}s elapsed", end="\r", flush=True)
        print()
    else:
        log("Orchestrator", "[INFO] No code changes -- skipping git push.")

    # Phase 3: Monitor loop
    log("Orchestrator", "--- Phase 3: Health Monitoring ---")
    for attempt in range(1, 6):
        log("Orchestrator", f"Health check {attempt}/5 ...")
        status = agent_monitor()

        if status == "HEALTHY":
            log("Orchestrator", "[SUCCESS] Space is HEALTHY. All done!")
            break

        elif status in ("DB_WIPED", "MFA_DRIFT"):
            log("Orchestrator", "[ACTION] DB wiped by rebuild -- sending reset pulse...")
            agent_reset_pulse()
            log("Orchestrator", "")
            log("Orchestrator", "=" * 58)
            log("Orchestrator", "  ACTION REQUIRED (takes < 60 seconds):")
            log("Orchestrator", "  1. Open HF Space in browser")
            log("Orchestrator", "  2. Click 'Create account' tab")
            log("Orchestrator", "  3. Register with your email + new password")
            log("Orchestrator", "  4. Scan the NEW QR code in Microsoft Authenticator")
            log("Orchestrator", "     (add as a NEW account -- do not reuse old entry)")
            log("Orchestrator", "  5. Enter the 6-digit code to complete MFA setup")
            log("Orchestrator", "=" * 58)
            break

        elif status == "BUILD_ERROR":
            log("Orchestrator", f"[WARN] Build error. Waiting 60s before retry {attempt}...")
            time.sleep(60)

        else:
            log("Orchestrator", f"[WARN] Status={status}. Waiting 30s...")
            time.sleep(30)

    log("Orchestrator", "")
    log("Orchestrator", "--- Patches Applied ---")
    if result["changes"]:
        for c in result["changes"]:
            log("Orchestrator", f"  [OK] {c}")
    else:
        log("Orchestrator", "  [INFO] No patches needed -- auth.py was already optimal.")

    log("Orchestrator", "Full log saved to: agent_healer.log")
    log("Orchestrator", "--- Agent workforce complete ---")

if __name__ == "__main__":
    main()
