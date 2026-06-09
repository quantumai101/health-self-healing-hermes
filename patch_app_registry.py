"""
patch_app_registry.py -- Adds CTCA Panel View to app.py page registry.
Run from project root: python patch_app_registry.py
"""
import sys, subprocess, shutil
from pathlib import Path

APP = Path("app.py")
if not APP.exists():
    print("ERROR: app.py not found.")
    sys.exit(1)

bak = APP.with_suffix(".py.bak_registry")
shutil.copy2(APP, bak)
print(f"OK: Backup saved to {bak}")

src = APP.read_text(encoding="utf-8")

# The line just before the warning is the insertion point
OLD = '        st.warning("Selected page not found in navigation registry.")'
NEW = ('        elif "CTCA Panel View" in page:\n'
       '            from pages.ctca_panel_viewer import render\n'
       '            render()\n'
       '        else:\n'
       '            st.warning("Selected page not found in navigation registry.")')

if OLD not in src:
    print("ERROR: Could not find insertion point in app.py.")
    print("Please add manually before the st.warning line:")
    print('        elif "CTCA Panel View" in page:')
    print('            from pages.ctca_panel_viewer import render')
    print('            render()')
    sys.exit(1)

patched = src.replace(OLD, NEW)
APP.write_text(patched, encoding="utf-8")
print("OK: app.py patched -- CTCA Panel View added to registry.")

for cmd, desc in [
    (["git", "add", "app.py"], "Staged app.py"),
    (["git", "commit", "-m", "fix: register CTCA Panel View in app.py navigation"], "Committed"),
    (["git", "push", "huggingface", "main"], "Pushed HF"),
    (["git", "push", "origin", "main"], "Pushed GitHub"),
]:
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 or "nothing to commit" in r.stdout + r.stderr
    print(f"{'OK' if ok else 'WARN'}: {desc}" + ("" if ok else f" -- {r.stderr.strip()[:80]}"))

print("DONE: Wait 60s then click CTCA Panel View in the sidebar.")
