"""
agents/medical_vision_agent.py
HERMES VISION — Medical Image Analysis Agent.
Uses llava:7b via local Ollama API (no GPU, no API key, 100% free).
Fixes: JPEG Lossless decompression via pylibjpeg/gdcm fallback chain.
Output: Saves both ctca_result.txt AND a rich HTML report matching MRA style.
"""

import base64
import json
import os
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── Safe add_log ──────────────────────────────────────────────────────────────
try:
    from core.session import add_log
except Exception:
    def add_log(msg: str) -> None:
        print(f"[HERMES_VISION] {msg}")

# ── Ollama ─────────────────────────────────────────────────────────────────────
OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava:7b"

VISION_SYSTEM_PROMPT = """You are HERMES VISION, a medical image analysis specialist.
When given a medical report image, you extract and structure ALL visible text and findings.
You identify: patient details (anonymised), scan type, clinical findings, measurements,
radiologist conclusions, and any flagged abnormalities.
Always output structured text so downstream agents can process it programmatically.
Never fabricate findings — only report what is visible in the image."""

# ── fastView paths ────────────────────────────────────────────────────────────
FASTVIEW_PATHS = [
    r"I:\CTCA Heart Scan DVD 20April2026\fastView\fastView.exe",
    r"I:\fastView\fastView.exe",
    r"C:\Program Files\Siemens\syngo fastView\fastView.exe",
    r"C:\Program Files (x86)\Siemens\syngo fastView\fastView.exe",
]

# ── Cardiac CT window presets (Hounsfield Units) ──────────────────────────────
WINDOW_PRESETS = {
    "cardiac":     {"center": 200,  "width": 700},
    "lung":        {"center": -600, "width": 1500},
    "soft_tissue": {"center": 40,   "width": 400},
    "bone":        {"center": 400,  "width": 1800},
}

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# Patient info (from fastView browser)
PATIENT = {
    "name":   "Zhang, Zhiming",
    "dob":    "1955-03-14",
    "age":    71,
    "gender": "Male",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _image_to_base64(image_path: Path) -> tuple:
    ext = image_path.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg", ".webp": "image/webp", ".bmp": "image/bmp"}
    mime_type = mime_map.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64, mime_type


def _apply_window(arr, center, width):
    import numpy as np
    low  = center - width / 2
    high = center + width / 2
    arr  = arr.astype(float)
    arr  = np.clip(arr, low, high)
    arr  = (arr - low) / (high - low) * 255
    return arr.astype("uint8")


def _dicom_to_png(dcm_path: Path, out_path: Path, preset: str = "cardiac") -> bool:
    """
    Convert DICOM to windowed PNG.
    Handles JPEG Lossless via pylibjpeg or gdcm handler chain.
    """
    try:
        import pydicom
        import numpy as np
        from PIL import Image

        # Try to register available decompression handlers
        try:
            import pydicom.config
            # Prefer pylibjpeg if installed
            try:
                from pydicom.pixel_data_handlers import pylibjpeg_handler
                pydicom.config.pixel_data_handlers = [pylibjpeg_handler]
            except ImportError:
                pass
            # Fall back to gdcm if available
            try:
                from pydicom.pixel_data_handlers import gdcm_handler
                if not any("pylibjpeg" in str(h) for h in pydicom.config.pixel_data_handlers):
                    pydicom.config.pixel_data_handlers = [gdcm_handler]
            except ImportError:
                pass
        except Exception:
            pass

        ds = pydicom.dcmread(str(dcm_path), force=True)
        if not hasattr(ds, "pixel_array"):
            return False

        arr = ds.pixel_array.astype(float)

        slope     = float(getattr(ds, "RescaleSlope",     1))
        intercept = float(getattr(ds, "RescaleIntercept", 0))
        arr = arr * slope + intercept

        wc = getattr(ds, "WindowCenter", None)
        ww = getattr(ds, "WindowWidth",  None)
        if wc is not None and ww is not None:
            center = float(wc[0] if hasattr(wc, "__len__") else wc)
            width  = float(ww[0] if hasattr(ww, "__len__") else ww)
        else:
            p      = WINDOW_PRESETS.get(preset, WINDOW_PRESETS["cardiac"])
            center = p["center"]
            width  = p["width"]

        arr = _apply_window(arr, center, width)

        if arr.ndim == 3 and arr.shape[0] > 3:
            arr = arr[arr.shape[0] // 2]

        if arr.ndim == 2:
            img = Image.fromarray(arr, mode="L").convert("RGB")
        elif arr.ndim == 3 and arr.shape[2] in (3, 4):
            img = Image.fromarray(arr)
        else:
            return False

        img.save(str(out_path), "PNG")
        return True

    except Exception as e:
        add_log(f"HERMES_VISION:dicom_to_png error {dcm_path.name}: {e}")
        return False


def _call_llava(image_b64: str, prompt: str, timeout: int = 180) -> str:
    payload = json.dumps({
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        OLLAMA_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("response", "No response from llava.")
    except urllib.error.URLError as e:
        return f"❌ Cannot reach Ollama.\nRun: ollama serve\nError: {e}"
    except Exception as e:
        return f"❌ Unexpected error calling llava: {e}"


def _find_fastview():
    for p in FASTVIEW_PATHS:
        if Path(p).exists():
            return p
    return None


def _pdf_to_images(pdf_path: Path) -> list:
    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=200)
        out_paths = []
        for i, img in enumerate(images):
            out = pdf_path.parent / f"_tmp_page_{i+1}.png"
            img.save(str(out), "PNG")
            out_paths.append(out)
        return out_paths
    except Exception:
        return []


# ── HTML report generator ──────────────────────────────────────────────────────

HTML_CSS = """
:root{
  --bg:#0d1117; --s:#161b22; --b:#30363d; --t:#e6edf3; --m:#8b949e;
  --a:#58a6ff;  --g:#3fb950; --y:#d29922; --r:#f85149;
  --highlight-bg:#1c2333;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--t);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;line-height:1.6;padding:2rem}
.hdr{background:linear-gradient(135deg,#1a1a2e,#16213e,#0f3460);border-radius:12px;padding:2rem;margin-bottom:2rem}
.hdr h1{font-size:1.8rem;color:#fff;margin-bottom:.5rem}
.hdr .m{color:#a8c8f8;font-size:.9rem}
.version-badge{display:inline-block;background:#1b4f72;color:#aed6f1;font-size:.75rem;padding:.15rem .5rem;border-radius:4px;margin-left:.5rem;vertical-align:middle}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}
.stat{background:var(--s);border:1px solid var(--b);border-radius:8px;padding:1rem;text-align:center}
.stat .v{font-size:2rem;font-weight:700;color:var(--a)}
.stat .l{font-size:.8rem;color:var(--m)}
.sec{background:var(--s);border:1px solid var(--b);border-radius:12px;padding:1.5rem;margin-bottom:1.5rem}
h2{color:var(--a);font-size:1.2rem;margin:1rem 0 .5rem;border-bottom:1px solid var(--b);padding-bottom:.5rem}
h3{color:#79c0ff;font-size:1rem;margin:.8rem 0 .3rem}
p{margin:.5rem 0} li{margin:.25rem 0 .25rem 1.5rem}
strong{color:#f0f6fc} hr{border:none;border-top:1px solid var(--b);margin:1rem 0}
table{width:100%;border-collapse:collapse;margin:.5rem 0;font-size:.9rem}
th{background:#21262d;color:var(--a);padding:.5rem;text-align:left}
td{padding:.4rem .5rem;border-bottom:1px solid var(--b);vertical-align:top}
tr:hover td{background:#21262d}
.val-red{color:var(--r);font-weight:600} .val-orange{color:#f0883e;font-weight:600}
.val-yellow{color:var(--y);font-weight:600} .val-green{color:var(--g)}
.badge-red{display:inline-block;background:#3d0e0e;color:#f85149;border:1px solid #f8514955;border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700}
.badge-orange{display:inline-block;background:#2d1a08;color:#f0883e;border:1px solid #f0883e55;border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700}
.badge-yellow{display:inline-block;background:#2d2008;color:#d29922;border:1px solid #d2992255;border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700}
.badge-green{display:inline-block;background:#0d2818;color:#3fb950;border:1px solid #3fb95055;border-radius:12px;padding:.05rem .55rem;font-size:.78rem;font-weight:700}
.card{background:#0d1117;border:1px solid var(--b);border-radius:10px;margin-bottom:1rem;overflow:hidden}
.card-header{background:var(--s);padding:.75rem 1rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.badge-ok{background:#1a472a;color:var(--g);padding:.2rem .5rem;border-radius:4px;font-size:.8rem;font-weight:700}
.badge-err{background:#4a1a1a;color:var(--r);padding:.2rem .5rem;border-radius:4px;font-size:.8rem;font-weight:700}
.slice-body{padding:1rem}
.note-box{background:#0d2137;border:1px solid #1f4a7a;border-radius:8px;padding:.75rem 1rem;margin-bottom:1.5rem;font-size:.85rem;color:#90caf9}
.disc{background:#1a0a0a;border:1px solid #f8514933;border-radius:8px;padding:1rem;color:var(--r);font-size:.85rem;margin-top:2rem}
.flag-box{border-radius:8px;padding:1rem;margin-bottom:.75rem}
.flag-red{background:#1a0000;border:1px solid #f8514933}
.flag-orange{background:#1a0d00;border:1px solid #f0883e33}
.flag-green{background:#001a08;border:1px solid #3fb95033}
"""


def _parse_llava_findings(raw: str) -> dict:
    """
    Parse llava free-text response into structured cardiac fields.
    Returns dict with keys: orientation, anatomy, quality, abnormalities, impression.
    """
    lines = raw.strip().split("\n")
    result = {
        "orientation":    "N/A",
        "anatomy":        "N/A",
        "quality":        "N/A",
        "abnormalities":  "N/A",
        "impression":     "N/A",
        "raw":            raw,
    }
    current = None
    buf = []

    key_map = {
        "1.": "orientation", "scan type": "orientation", "orientation": "orientation",
        "2.": "anatomy",     "anatomy": "anatomy",       "visible anatomy": "anatomy",
        "3.": "quality",     "image quality": "quality", "quality": "quality",
        "4.": "abnormalities", "abnormalities": "abnormalities", "visible abnorm": "abnormalities",
        "5.": "impression",  "impression": "impression", "overall": "impression",
    }

    for line in lines:
        lower = line.lower().strip()
        matched = None
        for k, v in key_map.items():
            if lower.startswith(k):
                matched = v
                break
        if matched:
            if current and buf:
                result[current] = " ".join(buf).strip()
            current = matched
            buf = [line.split(":", 1)[-1].strip() if ":" in line else ""]
        elif current:
            buf.append(line.strip())

    if current and buf:
        result[current] = " ".join(buf).strip()

    return result


def _severity_badge(text: str) -> str:
    """Return HTML badge based on keywords in text."""
    t = text.lower()
    if any(w in t for w in ["calcif", "stenosis", "occlusion", "infarct", "effusion", "critical", "severe"]):
        return "<span class='badge-red'>🔴 Abnormal</span>"
    if any(w in t for w in ["mild", "slight", "borderline", "minimal", "possible"]):
        return "<span class='badge-yellow'>🟡 Mild</span>"
    if any(w in t for w in ["normal", "patent", "no abnorm", "clear", "good", "n/a"]):
        return "<span class='badge-green'>🟢 Normal</span>"
    return "<span class='badge-orange'>🟠 Review</span>"


def _generate_html_report(
    folder_path: str,
    all_files_count: int,
    sampled_count: int,
    sample_every: int,
    max_slices: int,
    window_preset: str,
    slice_results: list,   # list of dicts: {label, success, raw, parsed, error}
    output_path: str,
) -> str:
    """Generate a rich HTML report matching the MRA Analysis Report style."""

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ok_count  = sum(1 for s in slice_results if s.get("success"))
    err_count = len(slice_results) - ok_count

    # Collect red/orange/green flags from parsed findings
    red_flags    = []
    orange_flags = []
    green_flags  = []

    for s in slice_results:
        if not s.get("success"):
            continue
        p = s.get("parsed", {})
        ab = p.get("abnormalities", "")
        im = p.get("impression", "")
        if any(w in (ab + im).lower() for w in ["calcif", "stenosis", "occlusion", "effusion", "severe"]):
            red_flags.append(f"{s['label']}: {ab[:120]}")
        elif any(w in (ab + im).lower() for w in ["mild", "borderline", "possible"]):
            orange_flags.append(f"{s['label']}: {ab[:120]}")
        else:
            green_flags.append(f"{s['label']}: {im[:120] or 'No significant abnormality detected'}")

    # Build slice cards HTML
    cards_html = ""
    for s in slice_results:
        if not s.get("success"):
            cards_html += f"""
<div class='card'>
  <div class='card-header'>
    <span class='badge-err'>✗</span>
    <strong>{s['label']}</strong>
  </div>
  <div class='slice-body'>
    <p style='color:#f85149'>{s.get('error','Unknown error')}</p>
  </div>
</div>"""
            continue

        p = s.get("parsed", {})
        badge = _severity_badge(p.get("abnormalities","") + p.get("impression",""))

        cards_html += f"""
<div class='card'>
  <div class='card-header'>
    <span class='badge-ok'>✓</span>
    <strong>{s['label']}</strong>
    {badge}
  </div>
  <div class='slice-body'>
    <table>
      <tr><th style='width:22%'>Parameter</th><th>Finding</th><th style='width:25%'>Normal (Cardiac CT)</th></tr>
      <tr>
        <td>Orientation</td>
        <td>{p.get('orientation','N/A')}</td>
        <td style='color:#8b949e'>Axial (typical CTCA)</td>
      </tr>
      <tr>
        <td>Visible Anatomy</td>
        <td>{p.get('anatomy','N/A')}</td>
        <td style='color:#8b949e'>Heart chambers, aorta, coronary arteries</td>
      </tr>
      <tr>
        <td>Image Quality</td>
        <td>{p.get('quality','N/A')}</td>
        <td style='color:#8b949e'>Good, no artefacts</td>
      </tr>
      <tr>
        <td>Abnormalities</td>
        <td class='{"val-red" if "🔴" in badge else "val-yellow" if "🟡" in badge else "val-green"}'>{p.get('abnormalities','N/A')}</td>
        <td style='color:#8b949e'>None</td>
      </tr>
      <tr>
        <td>Overall Impression</td>
        <td><strong>{p.get('impression','N/A')}</strong></td>
        <td style='color:#8b949e'>Normal cardiac anatomy</td>
      </tr>
    </table>
    <details style='margin-top:.75rem'>
      <summary style='cursor:pointer;color:#8b949e;font-size:.85rem'>▶ Raw llava:7b response</summary>
      <pre style='background:#0d1117;padding:.75rem;border-radius:6px;font-size:.78rem;color:#8b949e;white-space:pre-wrap;margin-top:.5rem'>{s.get('raw','').replace('<','&lt;').replace('>','&gt;')}</pre>
    </details>
  </div>
</div>"""

    # Flags section
    flags_html = ""
    if red_flags:
        items = "".join(f"<li>{f}</li>" for f in red_flags)
        flags_html += f"<div class='flag-box flag-red'><h3>🔴 Red Flags — Requires Review</h3><ul>{items}</ul></div>"
    if orange_flags:
        items = "".join(f"<li>{f}</li>" for f in orange_flags)
        flags_html += f"<div class='flag-box flag-orange'><h3>🟠 Orange Flags — Monitor</h3><ul>{items}</ul></div>"
    if green_flags:
        items = "".join(f"<li>{f}</li>" for f in green_flags)
        flags_html += f"<div class='flag-box flag-green'><h3>🟢 Green Flags — Normal</h3><ul>{items}</ul></div>"
    if not flags_html:
        flags_html = "<p style='color:#8b949e'>Analysis incomplete — see slice errors above.</p>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>CTCA Heart Scan Analysis — {PATIENT['name']}</title>
<style>{HTML_CSS}</style>
</head>
<body>

<div class="hdr">
  <h1>❤️ CTCA Heart Scan Analysis Report
    <span class="version-badge">20 April 2026</span>
  </h1>
  <div class="m">
    <strong>{PATIENT['name']}</strong> | DOB: {PATIENT['dob']} | Age: {PATIENT['age']} | {PATIENT['gender']}<br>
    Scan: 20 April 2026 | CTCA — CT Coronary Angiogram | Siemens Quantum<br>
    Modality: CT | Series: BestDiast 73% Ca, Soft BestDiast 74%, Sharp 73% ZF CTC, Lung BestDiast 74%<br>
    Generated: {now} | AI Model: {OLLAMA_MODEL} (local Ollama) | Window preset: {window_preset}
  </div>
</div>

<div class="note-box">
  <strong>📌 Study Note:</strong>
  CTCA performed 20 April 2026 on Siemens Quantum scanner. This report covers
  {sampled_count} sampled DICOM slices from {all_files_count} total files in series 16080000.
  Folder: <code>{folder_path}</code><br>
  <strong>⚠️ Limitation:</strong> This AI analysis uses llava:7b vision model on sampled slices.
  It is <em>not a substitute for radiologist review</em>. All findings should be clinically correlated.
</div>

<div class="stats">
  <div class="stat"><div class="v">{all_files_count}</div><div class="l">Total DICOM Files</div></div>
  <div class="stat"><div class="v">{sampled_count}</div><div class="l">Slices Analysed</div></div>
  <div class="stat"><div class="v">{ok_count}</div><div class="l">Successfully Read</div></div>
  <div class="stat"><div class="v">{err_count}</div><div class="l">Errors</div></div>
</div>

<div class="sec">
  <h2>🏥 Coronary Artery Overview</h2>
  <table>
    <tr>
      <th>Structure</th><th>AI Finding</th>
      <th>Normal Reference</th><th>Rating</th>
    </tr>
    <tr>
      <td>Left Main (LM)</td>
      <td>See slice findings below</td>
      <td style='color:#8b949e'>Patent, no stenosis</td>
      <td>—</td>
    </tr>
    <tr>
      <td>LAD (Left Anterior Descending)</td>
      <td>See slice findings below</td>
      <td style='color:#8b949e'>Patent, no stenosis</td>
      <td>—</td>
    </tr>
    <tr>
      <td>LCx (Left Circumflex)</td>
      <td>See slice findings below</td>
      <td style='color:#8b949e'>Patent, no stenosis</td>
      <td>—</td>
    </tr>
    <tr>
      <td>RCA (Right Coronary Artery)</td>
      <td>See slice findings below</td>
      <td style='color:#8b949e'>Patent, no stenosis</td>
      <td>—</td>
    </tr>
    <tr>
      <td>Aortic Root</td>
      <td>See slice findings below</td>
      <td style='color:#8b949e'>&lt; 40mm diameter</td>
      <td>—</td>
    </tr>
    <tr>
      <td>Pericardium</td>
      <td>See slice findings below</td>
      <td style='color:#8b949e'>No effusion</td>
      <td>—</td>
    </tr>
    <tr>
      <td>Heart Chambers</td>
      <td>See slice findings below</td>
      <td style='color:#8b949e'>Normal size and function</td>
      <td>—</td>
    </tr>
    <tr>
      <td>Calcium Score (Agatston)</td>
      <td>Not quantified (requires dedicated Ca scoring series)</td>
      <td style='color:#8b949e'>&lt; 100 = low risk</td>
      <td>—</td>
    </tr>
  </table>
  <p style='color:#8b949e;font-size:.85rem;margin-top:.5rem'>
    ℹ️ Detailed per-vessel findings require radiologist review of all series.
    AI analysis below is based on {sampled_count} sampled axial slices only.
  </p>
</div>

<div class="sec">
  <h2>🚩 Summary Flags</h2>
  {flags_html}
</div>

<div class="sec">
  <h2>🔬 Per-Slice AI Findings</h2>
  <p style='color:#8b949e;font-size:.85rem;margin-bottom:1rem'>
    Sampling: every {sample_every}th file, max {max_slices} slices.
    Window preset: <strong>{window_preset}</strong> (center={WINDOW_PRESETS.get(window_preset,{}).get('center','?')} HU,
    width={WINDOW_PRESETS.get(window_preset,{}).get('width','?')} HU).
  </p>
  {cards_html}
</div>

<div class="sec">
  <h2>📋 Recommended Next Steps</h2>
  <ol style='margin-left:1.5rem'>
    <li style='margin-bottom:.5rem'>
      <strong>Radiologist formal report</strong> — this AI summary does not replace a qualified
      radiologist's interpretation of all 9 CTCA series.
    </li>
    <li style='margin-bottom:.5rem'>
      <strong>Calcium scoring</strong> — open the "BestDiast 73% Ca" series in Syngo fastView
      and request formal Agatston score calculation.
    </li>
    <li style='margin-bottom:.5rem'>
      <strong>Coronary stenosis grading</strong> — the "Sharp 73% ZF CTC" series provides
      highest resolution for stenosis assessment; review with MPR/CPR reconstructions.
    </li>
    <li style='margin-bottom:.5rem'>
      <strong>Lung fields</strong> — review "Lung BestDiast 74%" series for incidental
      pulmonary findings.
    </li>
    <li style='margin-bottom:.5rem'>
      <strong>Improve AI analysis</strong> — export PNGs from fastView for all series,
      then run: <code>agent.analyse_folder_of_images('I:/CTCA Heart Scan DVD 20April2026/ctca_exports/')</code>
    </li>
  </ol>
</div>

<div class="disc">
  <strong>⚠️ DISCLAIMER:</strong> This report is generated by HERMES VISION AI using llava:7b
  on {sampled_count} sampled DICOM slices. It is <strong>not a medical device</strong> and is
  <strong>not intended for diagnostic use</strong>. All findings require clinical correlation
  and radiologist review. "syngo fastView is not a medical device" — Siemens Healthcare GmbH, 2016.
</div>

</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return html


# ── Main Agent Class ───────────────────────────────────────────────────────────

class MedicalVisionAgent:
    name = "HERMES VISION"
    icon = "🔬"
    role = "Medical Image Analysis"

    TRIGGER_COMMANDS = [
        "Analyse medical report image",
        "Extract findings from scan",
        "Read medical image report",
    ]

    # ── fastView ───────────────────────────────────────────────────────────────

    def open_in_fastview(self, dicom_path: str = None) -> str:
        exe = _find_fastview()
        if not exe:
            return (
                "❌ Syngo fastView not found.\nExpected:\n" +
                "\n".join(f"  {p}" for p in FASTVIEW_PATHS)
            )
        try:
            cmd = [exe]
            if dicom_path and Path(dicom_path).exists():
                cmd.append(str(dicom_path))
            subprocess.Popen(cmd, shell=False)
            add_log(f"HERMES_VISION:fastview_launched:{exe}")
            return f"✅ Syngo fastView launched!\n{'Loading: ' + dicom_path if dicom_path else 'Use Patient > Open Patient Browser.'}"
        except Exception as e:
            return f"❌ Failed to launch fastView: {e}"

    def fastview_export_guide(self) -> str:
        return """
## Export CTCA PNGs from Syngo fastView → HERMES VISION

Step 1 — Launch fastView:
  agent.open_in_fastview()

Step 2 — In fastView:
  Patient > Open Patient Browser > ZHANG,ZHIMING > Open Study
  Choose series: BestDiast 73% Ca  (or Sharp 73% ZF CTC for vessel detail)

Step 3 — Export:
  Patient > Save as... > PNG
  Save to: I:\\CTCA Heart Scan DVD 20April2026\\ctca_exports\\

Step 4 — Analyse:
  agent.analyse_folder_of_images(
      'I:/CTCA Heart Scan DVD 20April2026/ctca_exports/',
      max_images=10,
      series_name='BestDiast 73%'
  )
"""

    # ── Analyse exported PNG folder ────────────────────────────────────────────

    def analyse_folder_of_images(
        self,
        folder_path:  str,
        sample_every: int = 1,
        max_images:   int = 10,
        series_name:  str = "CTCA",
        save_html:    bool = True,
    ) -> str:
        add_log(f"HERMES_VISION:image_folder:{folder_path}")
        folder = Path(folder_path)
        if not folder.exists():
            return f"❌ Folder not found: {folder_path}"

        images = sorted([
            f for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
        ])
        if not images:
            return f"❌ No PNG/JPG images found in: {folder_path}"

        sampled       = images[::sample_every][:max_images]
        slice_results = []

        for i, img_path in enumerate(sampled):
            label = f"Image {i+1}/{len(sampled)}: {img_path.name}"
            add_log(f"HERMES_VISION:analysing {label}")
            raw = self.analyse_image(str(img_path), custom_prompt=(
                f"{VISION_SYSTEM_PROMPT}\n\n"
                f"This is {label} from a {series_name} CTCA cardiac CT scan.\n"
                "Please identify:\n"
                "1. SCAN TYPE & ORIENTATION (axial / sagittal / coronal)\n"
                "2. VISIBLE ANATOMY (heart chambers, aorta, coronary arteries, pericardium)\n"
                "3. IMAGE QUALITY (good / poor / artefacts)\n"
                "4. VISIBLE ABNORMALITIES "
                "(coronary calcification, stenosis, lesions, pericardial effusion)\n"
                "5. OVERALL IMPRESSION\n"
            ))
            slice_results.append({
                "label":   label,
                "success": True,
                "raw":     raw,
                "parsed":  _parse_llava_findings(raw),
                "error":   None,
            })

        txt = self._format_txt(folder_path, len(images), len(sampled), sample_every, max_images, "exported_png", slice_results)

        if save_html:
            html_path = str(folder / "CTCA_Analysis_Report.html")
            _generate_html_report(folder_path, len(images), len(sampled), sample_every, max_images,
                                  "exported_png", slice_results, html_path)
            txt += f"\n\n✅ HTML report saved: {html_path}"

        return txt

    # ── DICOM folder ───────────────────────────────────────────────────────────

    def analyse_dicom_folder(
        self,
        folder_path:   str,
        sample_every:  int = 10,
        max_slices:    int = 5,
        window_preset: str = "cardiac",
        save_html:     bool = True,
    ) -> str:
        import tempfile
        add_log(f"HERMES_VISION:dicom_folder:{folder_path} preset={window_preset}")

        folder = Path(folder_path)
        if not folder.exists():
            return f"❌ Folder not found: {folder_path}"

        try:
            import pydicom
            import numpy as np
            from PIL import Image
        except ImportError as e:
            return (
                f"❌ Missing dependency: {e}\n"
                f"Run: pip install pydicom pillow numpy --break-system-packages"
            )

        all_files = sorted([f for f in folder.iterdir() if f.is_file() and f.suffix == ""])
        if not all_files:
            all_files = sorted([f for f in folder.iterdir() if f.is_file()])
        if not all_files:
            return f"❌ No files found in: {folder_path}"

        sampled       = all_files[::sample_every][:max_slices]
        slice_results = []
        tmp_dir       = Path(tempfile.mkdtemp())

        add_log(f"HERMES_VISION:total={len(all_files)},sampled={len(sampled)}")

        for i, dcm_path in enumerate(sampled):
            label   = f"Slice {i+1}/{len(sampled)} (file: {dcm_path.name})"
            tmp_img = tmp_dir / f"slice_{i+1}.png"

            ok = _dicom_to_png(dcm_path, tmp_img, preset=window_preset)
            if not ok:
                slice_results.append({
                    "label":   label,
                    "success": False,
                    "raw":     "",
                    "parsed":  {},
                    "error":   (
                        "Could not render DICOM pixel data. "
                        "Install JPEG Lossless support: "
                        "pip install pylibjpeg pylibjpeg-libjpeg --break-system-packages"
                    ),
                })
                continue

            add_log(f"HERMES_VISION:analysing {label}")
            try:
                b64, _ = _image_to_base64(tmp_img)
                raw = _call_llava(b64, prompt=(
                    f"{VISION_SYSTEM_PROMPT}\n\n"
                    f"This is {label} from a CTCA (CT Coronary Angiogram). "
                    f"Window: {window_preset}.\n"
                    "Please identify:\n"
                    "1. SCAN TYPE & ORIENTATION (axial / sagittal / coronal)\n"
                    "2. VISIBLE ANATOMY "
                    "(heart chambers, aorta, coronary arteries, pericardium)\n"
                    "3. IMAGE QUALITY (good / poor / motion artefacts / noise)\n"
                    "4. VISIBLE ABNORMALITIES "
                    "(coronary calcification, stenosis, lesions, pericardial effusion, "
                    "aortic dilation)\n"
                    "5. OVERALL IMPRESSION\n"
                    "If image is dark/unclear state that — may need different window preset."
                ))
                slice_results.append({
                    "label":   label,
                    "success": True,
                    "raw":     raw,
                    "parsed":  _parse_llava_findings(raw),
                    "error":   None,
                })
            except Exception as e:
                slice_results.append({
                    "label":   label,
                    "success": False,
                    "raw":     "",
                    "parsed":  {},
                    "error":   str(e),
                })

            try:
                tmp_img.unlink()
            except Exception:
                pass

        try:
            tmp_dir.rmdir()
        except Exception:
            pass

        txt = self._format_txt(folder_path, len(all_files), len(sampled),
                               sample_every, max_slices, window_preset, slice_results)

        if save_html:
            # Save HTML alongside DICOM folder parent
            parent = Path(folder_path).parent.parent  # I:\CTCA Heart Scan DVD 20April2026
            html_path = str(parent / "CTCA_Analysis_Report.html")
            _generate_html_report(folder_path, len(all_files), len(sampled),
                                  sample_every, max_slices, window_preset,
                                  slice_results, html_path)
            txt += f"\n\n✅ HTML report saved: {html_path}"

        return txt

    def _format_txt(self, folder_path, total, sampled, every, max_s, preset, results):
        lines = [
            f"# HERMES VISION — CTCA Heart Scan Analysis",
            f"Folder: {folder_path}",
            f"Total: {total} | Sampled: {sampled} (every {every}th, max {max_s})",
            f"Window: {preset} | Model: {OLLAMA_MODEL}",
            "", "---", "",
        ]
        for s in results:
            lines.append(f"### {s['label']}")
            if s["success"]:
                p = s["parsed"]
                lines += [
                    f"Orientation:   {p.get('orientation','N/A')}",
                    f"Anatomy:       {p.get('anatomy','N/A')}",
                    f"Quality:       {p.get('quality','N/A')}",
                    f"Abnormalities: {p.get('abnormalities','N/A')}",
                    f"Impression:    {p.get('impression','N/A')}",
                ]
            else:
                lines.append(f"❌ {s['error']}")
            lines += ["", "---", ""]
        return "\n".join(lines)

    # ── Single image ───────────────────────────────────────────────────────────

    def analyse_image(self, image_path: str, custom_prompt: str = None) -> str:
        add_log(f"HERMES_VISION:analyse:{Path(image_path).name}")
        path = Path(image_path)
        if not path.exists():
            return f"❌ File not found: {image_path}"
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return f"❌ Unsupported format: {path.suffix}"
        try:
            b64, _ = _image_to_base64(path)
        except Exception as e:
            return f"❌ Could not read image: {e}"
        prompt = custom_prompt or (
            f"{VISION_SYSTEM_PROMPT}\n\n"
            "Analyse this medical image:\n"
            "1. REPORT TYPE\n2. PATIENT INFO (anonymised)\n3. SCAN REGION\n"
            "4. DATE OF SCAN\n5. KEY CLINICAL FINDINGS\n6. MEASUREMENTS\n"
            "7. RADIOLOGIST CONCLUSIONS\n8. FLAGGED ABNORMALITIES\n9. FOLLOW-UP\n"
            "Write N/A if not visible."
        )
        return _call_llava(b64, prompt)

    # ── PDF ────────────────────────────────────────────────────────────────────

    def analyse_pdf(self, pdf_path: str, custom_prompt: str = None) -> str:
        add_log(f"HERMES_VISION:pdf:{Path(pdf_path).name}")
        path = Path(pdf_path)
        if not path.exists():
            return f"❌ File not found: {pdf_path}"
        image_paths = _pdf_to_images(path)
        if not image_paths:
            return "❌ Could not convert PDF. Install pdf2image + poppler."
        results = []
        for i, img_path in enumerate(image_paths):
            results.append(f"### Page {i+1}\n{self.analyse_image(str(img_path), custom_prompt)}")
            try:
                img_path.unlink()
            except Exception:
                pass
        return "\n\n---\n\n".join(results)

    # ── Generic run ────────────────────────────────────────────────────────────

    def run(self, command: str) -> str:
        add_log(f"HERMES_VISION:{command[:60]}")
        if ":" in command:
            action, _, arg = command.partition(":")
            action = action.strip().lower()
            arg    = arg.strip()
            if action == "analyse":
                return (self.analyse_pdf(arg) if Path(arg).suffix.lower() == ".pdf"
                        else self.analyse_image(arg))
            if action == "dicom":
                return self.analyse_dicom_folder(arg)
            if action == "fastview":
                return self.open_in_fastview(arg)
            if action == "images":
                return self.analyse_folder_of_images(arg)
        return (
            "🔬 HERMES VISION — Usage:\n\n"
            "agent.analyse_dicom_folder('I:/CTCA Heart Scan DVD 20April2026/DICOM/26052505/16080000')\n"
            "agent.open_in_fastview()\n"
            "agent.analyse_folder_of_images('I:/CTCA Heart Scan DVD 20April2026/ctca_exports/')\n"
            "agent.analyse_image('path/to/image.png')\n"
            "agent.analyse_pdf('path/to/report.pdf')\n"
        )

    # ── SENTINEL ───────────────────────────────────────────────────────────────

    def extract_for_sentinel(self, image_path: str) -> str:
        raw = self.analyse_image(image_path, custom_prompt=(
            f"{VISION_SYSTEM_PROMPT}\n\n"
            "Analyse for compliance. Replace names with [PATIENT], IDs with [ID].\n"
            "1. Document type\n2. De-identified findings\n3. Sensitivity (HIGH/MEDIUM/LOW)\n"
            "4. PHI requiring redaction\n5. Compliance flags\n"
        ))
        return f"🔬 HERMES VISION → SENTINEL handoff:\n\n{raw}"
