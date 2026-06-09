"""
add_panel_to_nav.py -- Adds CTCA Panel View to sidebar navigation.
Run from project root: python add_panel_to_nav.py
"""
import sys, subprocess, shutil, re
from pathlib import Path

CFG = Path("core") / "config.py"
if not CFG.exists():
    print(f"ERROR: {CFG} not found.")
    sys.exit(1)

src = CFG.read_text(encoding="utf-8")

ENTRY_KEY   = '"CTCA Panel View"'
ENTRY_LINE  = '"CTCA Panel View": "pages/ctca_panel_viewer",'

if ENTRY_KEY in src:
    print("INFO: CTCA Panel View already in config -- checking nav order.")
else:
    # Backup
    bak = CFG.with_suffix(".py.bak_nav")
    shutil.copy2(CFG, bak)
    print(f"OK: Backed up config to {bak}")

    # Find the PAGES dict and insert before closing brace
    # Try inserting after last known page entry
    insert_after_candidates = [
        '"CTCA Viewer"',
        '"Imaging"',
        '"imaging"',
        '"Chat"',
        '"chat"',
        '"Dashboard"',
        '"dashboard"',
    ]

    inserted = False
    for candidate in insert_after_candidates:
        # Find line with this candidate and insert after it
        pattern = rf'({re.escape(candidate)}[^\n]*\n)'
        match = re.search(pattern, src)
        if match:
            insert_pos = match.end()
            src = src[:insert_pos] + f'    {ENTRY_LINE}\n' + src[insert_pos:]
            inserted = True
            print(f"OK: Inserted after {candidate} entry.")
            break

    if not inserted:
        # Fallback: insert before closing brace of PAGES dict
        pattern = r'(PAGES\s*=\s*\{[^}]*?)(\})'
        def add_entry(m):
            body = m.group(1).rstrip()
            if not body.endswith(','):
                body += ','
            return body + '\n    ' + ENTRY_LINE + '\n' + m.group(2)
        new_src = re.sub(pattern, add_entry, src, flags=re.DOTALL)
        if new_src != src:
            src = new_src
            inserted = True
            print("OK: Inserted via PAGES dict fallback.")

    if not inserted:
        print("ERROR: Could not locate PAGES dict. Add manually:")
        print(f'  {ENTRY_LINE}')
        sys.exit(1)

    CFG.write_text(src, encoding="utf-8")
    print("OK: core/config.py updated.")

# Git push
for cmd, desc in [
    (["git", "add", "core/config.py"], "Staged config"),
    (["git", "commit", "-m", "feat: add CTCA Panel View to sidebar nav"], "Committed"),
    (["git", "push", "huggingface", "main"], "Pushed HF"),
    (["git", "push", "origin", "main"], "Pushed GitHub"),
]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 or "nothing to commit" in r.stdout + r.stderr
    print(f"{'OK' if ok else 'WARN'}: {desc}" + ("" if ok else f" -- {r.stderr.strip()[:80]}"))

print("")
print("DONE: Wait 60s then refresh HF Space.")
print("Look for 'CTCA Panel View' in the left sidebar under NAVIGATION.")
print("It shows all 5 slices in a grid with fixed coloured annotation dots.")
