"""
fix_page_registry.py -- Finds the page registry in app.py and adds CTCA Panel View.
Run from project root: python fix_page_registry.py
"""
import sys, re, subprocess, shutil
from pathlib import Path

APP = Path("app.py")
if not APP.exists():
    print("ERROR: app.py not found. Run from project root.")
    sys.exit(1)

src = APP.read_text(encoding="utf-8")

# Show the registry section so we know the pattern
print("=== Current page registry in app.py ===")
lines = src.splitlines()
for i, line in enumerate(lines):
    if any(x in line for x in ["ctca", "imaging", "dashboard", "compliance",
                                 "chat", "news", "ehr", "page_map", "registry",
                                 "PAGE_MAP", "REGISTRY", "import_module",
                                 "pages/"]):
        print(f"  L{i+1}: {line}")
print("========================================")
