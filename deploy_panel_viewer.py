"""
deploy_panel_viewer.py -- Deploy CTCA multi-panel viewer as a new page.
Run from project root: python deploy_panel_viewer.py

What it does:
  1. Copies ctca_panel_viewer.py -> pages/ctca_panel_viewer.py
  2. Backs up core/config.py before touching it
  3. Adds "CTCA Panel View" to PAGES in core/config.py (if not already there)
  4. Git commits and pushes both remotes

Does NOT modify pages/chat.py or any other existing file.
"""
import sys, re, subprocess, shutil
from pathlib import Path

SRC  = Path("ctca_panel_viewer.py")
DEST = Path("pages") / "ctca_panel_viewer.py"
CFG  = Path("core") / "config.py"

# -- Step 1: copy new page ------------------------------------------------
if not SRC.exists():
    print(f"ERROR: {SRC} not found. Place it in project root first.")
    sys.exit(1)

shutil.copy2(SRC, DEST)
print(f"OK: Copied {SRC} -> {DEST}")

# -- Step 2: backup config then patch PAGES list --------------------------
if not CFG.exists():
    print(f"WARN: {CFG} not found -- skipping PAGES patch. Add manually.")
else:
    backup = CFG.with_suffix(".py.bak_panel")
    shutil.copy2(CFG, backup)
    print(f"OK: Config backed up to {backup}")

    cfg_src = CFG.read_text(encoding="utf-8")

    ENTRY = '"CTCA Panel View": "pages/ctca_panel_viewer"'
    if ENTRY in cfg_src:
        print("INFO: PAGES entry already present -- no config change needed.")
    else:
        # Try to insert after the last entry in the PAGES dict
        # Matches patterns like:  "Something": "pages/something",
        pattern = r'(PAGES\s*=\s*\{[^}]*?)(\})'
        def inserter(m):
            body = m.group(1).rstrip()
            # Add trailing comma to last entry if missing
            if body and not body.endswith(','):
                body += ','
            return body + '\n    ' + ENTRY + ',\n' + m.group(2)

        patched = re.sub(pattern, inserter, cfg_src, flags=re.DOTALL)
        if patched == cfg_src:
            print("WARN: Could not auto-patch PAGES dict -- add manually:")
            print(f'  {ENTRY}')
        else:
            CFG.write_text(patched, encoding="utf-8")
            print("OK: Added CTCA Panel View to PAGES in core/config.py")

# -- Step 3: git push -----------------------------------------------------
files_to_add = ["pages/ctca_panel_viewer.py"]
if CFG.exists() and ENTRY in CFG.read_text(encoding="utf-8"):
    files_to_add.append("core/config.py")

for cmd, desc in [
    (["git", "add"] + files_to_add,                                         "Staged files"),
    (["git", "commit", "-m", "feat: add CTCA multi-panel radiologist view"], "Committed"),
    (["git", "push", "huggingface", "main"],                                 "Pushed HF"),
    (["git", "push", "origin", "main"],                                      "Pushed GitHub"),
]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 or "nothing to commit" in r.stdout + r.stderr
    print(f"{'OK' if ok else 'WARN'}: {desc}" + ("" if ok else f" -- {r.stderr.strip()[:100]}"))

print("")
print("DONE. Wait 60s for HF rebuild.")
print("If CTCA Panel View does not appear in sidebar, add this to core/config.py PAGES dict:")
print('  "CTCA Panel View": "pages/ctca_panel_viewer",')
