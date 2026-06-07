"""
deploy_chat_fix.py -- Copies fixed chat.py into project and pushes to HF + GitHub.
Run from project root: python deploy_chat_fix.py
"""
import sys, shutil, subprocess
from pathlib import Path

SRC  = Path(__file__).parent / "chat.py"         # same folder as this script
DEST = Path("pages") / "chat.py"

if not SRC.exists():
    # Try sibling path if running from project root with script in root
    SRC = Path("chat.py")

if not SRC.exists():
    print(f"ERROR: chat.py source not found at {SRC}")
    sys.exit(1)

if not DEST.parent.exists():
    print(f"ERROR: pages/ directory not found. Run from project root.")
    sys.exit(1)

shutil.copy2(SRC, DEST)
print(f"OK: Copied {SRC} -> {DEST}")

cmds = [
    (["git", "add", "pages/chat.py"], "Staged pages/chat.py"),
    (["git", "commit", "-m", "fix(chat): render HTML viewer via components.html + simulation watermark"], "Committed"),
    (["git", "push", "huggingface", "main"], "Pushed -> huggingface"),
    (["git", "push", "origin", "main"],      "Pushed -> origin"),
]
for cmd, desc in cmds:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 or "nothing to commit" in r.stdout + r.stderr:
        print(f"OK: {desc}")
    else:
        print(f"WARN: {desc}: {r.stderr.strip()[:120]}")

print("DONE: Wait 60s for HF rebuild, then re-run the CTCA simulation.")
