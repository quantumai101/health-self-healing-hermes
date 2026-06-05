"""
pages/imaging.py — CTCA Slice Viewer with real DICOM background + hover tooltips
==================================================================================
Drop-in replacement for the existing imaging page.

Features added:
  • Loads actual DICOM slice JPEGs from CTCA_LOCAL_PATH (your I:/CTCA drive)
    and uses them as the canvas background behind the finding dots
  • Pulsing finding dots overlay the real anatomy
  • Hovering any dot PAUSES the animation and shows a clinical tooltip
  • Falls back to synthetic canvas if DICOM images can't be loaded
  • All rendering is in a single self-contained HTML component

Setup:
  In .env set:
    CTCA_LOCAL_PATH=I:/CTCA Heart Scan DVD DVD 20April2026/DICOM/26052505/16080000
  The viewer expects 5 JPEG exports named SL1.jpg … SL5.jpg in that folder.
  Export them from Syngo FastView: File → Save As → JPEG, name sequentially.
  If not found, synthetic mode activates automatically.
"""

import os
import base64
import json
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

# ── DICOM jpeg loader ─────────────────────────────────────────────────────────
def load_slice_images() -> list[str | None]:
    """
    Try to load SL1.jpg–SL5.jpg from CTCA slice folders.

    Search order (first path that contains SL1.jpg wins):
      1. CTCA_LOCAL_PATH  — your I:/CTCA drive (local dev)
      2. CTCA_DATA_PATH   — data/ctca_slices    (HuggingFace Spaces / git)

    .env example:
      CTCA_LOCAL_PATH=I:/CTCA Heart Scan DVD 20April2026/DICOM/26052505/16080000
      CTCA_DATA_PATH=data/ctca_slices

    Returns list of 5 base64 data-URIs (or None per slot if file missing).
    """
    # Build candidate paths — ignore empty / unset keys
    candidates = []
    for key in ("CTCA_LOCAL_PATH", "CTCA_DATA_PATH"):
        val = os.getenv(key, "").strip().strip('"')
        if val:
            candidates.append(Path(val))

    # Pick the first folder that actually contains SL1.jpg
    base = None
    for p in candidates:
        if (p / "SL1.jpg").exists():
            base = p
            break

    if base is None:
        return [None] * 5          # no images found — synthetic mode

    result = []
    for i in range(1, 6):
        p = base / f"SL{i}.jpg"
        if p.exists():
            with open(p, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            result.append(f"data:image/jpeg;base64,{b64}")
        else:
            result.append(None)
    return result


# ── Finding definitions (matches HERMES v2 report) ────────────────────────────
FINDINGS = [
    # ── 3-COLOUR HIGH-CONTRAST SYSTEM (matches image-2 bar chart palette) ──
    # 🔴 RED    (#FF4444 / #FF9999) = CRITICAL  / soft lipid plaque / alert
    # 🟡 YELLOW (#FFD700 / #FFE97A) = WARNING   / calcified plaque  / moderate
    # 🟢 GREEN  (#00C851 / #66E89A) = REFERENCE / FAI zone          / info
    #
    # All three maximally separated in hue AND luminance — identical to the
    # high-contrast bar-chart colours used in the Endeavour Energy dashboard.
    # ──────────────────────────────────────────────────────────────────────

    # slice_index (0-based), x%, y%, colour, pulse_colour, label, detail
    {
        "slice": 0, "x": 51, "y": 48,
        "colour":  "#FFD700",          # ── SHINING YELLOW — calcified, stable
        "pulse":   "#FFE97A",
        "label": "SL 1 — Calcified plaque at LMCA ostium",
        "detail": (
            "Left Main Coronary Artery ostium. "
            "Dense calcified plaque (HU ~450). "
            "Agatston contribution: minor. "
            "CAD-RADS 0 at LM — no stenosis."
        ),
        "severity": "warn",
    },
    {
        "slice": 1, "x": 48, "y": 44,
        "colour":  "#FFD700",          # ── SHINING YELLOW — calcified, moderate
        "pulse":   "#FFE97A",
        "label": "SL 2 — pLAD proximal calcification",
        "detail": (
            "Proximal LAD. Eccentric calcified plaque, arc 140°. "
            "HU core 420–510. Stenosis 17.3% geometric. "
            "Remodelling index 1.08. CAD-RADS 2."
        ),
        "severity": "warn",
    },
    {
        "slice": 2, "x": 46, "y": 46,
        "colour":  "#FF4444",          # ── BRIGHT RED — soft lipid, critical
        "pulse":   "#FF9999",
        "label": "SL 3 — Significant non-calcified plaque, mid LAD",
        "detail": (
            "Mid LAD segment. Soft lipid plaque, HU 40–80 pool. "
            "Estimated stenosis 60–70%. Eccentricity 0.44. "
            "pLAD FAI −68.4 HU — BORDERLINE ELEVATED. "
            "Independent MACE risk modifier."
        ),
        "severity": "alert",
    },
    {
        "slice": 3, "x": 55, "y": 50,
        "colour":  "#FFD700",          # ── SHINING YELLOW — soft plaque, mild
        "pulse":   "#FFE97A",
        "label": "SL 4 — mRCA soft plaque",
        "detail": (
            "Mid RCA. Minimal soft/lipid plaque. HU 65 (40–80 pool). "
            "Stenosis 12.1% geometric. Remodelling index 1.04. "
            "CAD-RADS 1. Non-obstructive."
        ),
        "severity": "warn",
    },
    {
        "slice": 4, "x": 52, "y": 52,
        "colour":  "#00C851",          # ── BRIGHT GREEN — FAI reference zone
        "pulse":   "#66E89A",
        "label": "SL 5 — FAI measurement zone pLAD",
        "detail": (
            "Perivascular fat attenuation index (FAI) measurement zone. "
            "pLAD FAI = −68.4 HU (threshold −70.1 HU). "
            "Borderline elevated. Associated with 9× increased fatal "
            "cardiac event risk vs normal FAI (Oikonomou et al. 2018)."
        ),
        "severity": "ok",
    },
]

SLICE_LABELS = [
    "77172526", "77172537", "77172548", "77172559", "77172570"
]


def render_viewer():
    st.markdown("#### ▼ Interactive CTCA Slice Viewer (Syngo Simulation)")

    slice_images = load_slice_images()
    has_real = any(img is not None for img in slice_images)

    # Pass data to JS
    findings_json = json.dumps(FINDINGS)
    labels_json   = json.dumps(SLICE_LABELS)
    images_json   = json.dumps(slice_images)   # list of data-URIs or null

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: #0d1117; font-family: 'Courier New', monospace;
          color: #e6edf3; user-select: none; }}

  #viewer-wrap {{
    display: flex; gap: 8px; padding: 8px;
    background: #0d1117;
  }}

  /* ── Main canvas area ─────────────────────────────────────────────────── */
  #canvas-col {{ flex: 1; }}

  #hdr {{
    background: #1c2128; border: 1px solid #30363d;
    padding: 4px 8px; font-size: 10px; color: #8b949e;
    display: flex; justify-content: space-between;
  }}
  #hdr b {{ color: #e6edf3; }}

  #canvas-wrap {{
    position: relative;
    width: 100%; aspect-ratio: 1 / 1;
    background: #000; overflow: hidden;
    border: 1px solid #30363d;
    cursor: crosshair;
  }}

  /* Real DICOM background image */
  #slice-img {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    object-fit: cover;
    opacity: 0.92;
    transition: opacity 0.3s;
  }}

  /* Synthetic SVG fallback (shown when no DICOM images) */
  #synthetic-svg {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
  }}

  /* Overlay canvas for dots */
  #dot-canvas {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    pointer-events: none;
  }}

  /* Individual dot elements — pointer-events ON */
  .finding-dot {{
    position: absolute;
    transform: translate(-50%, -50%);
    cursor: pointer;
    pointer-events: all;
  }}

  .dot-core {{
    width: 18px; height: 18px;
    border-radius: 50%;
    position: relative; z-index: 2;
    transition: transform 0.15s;
    /* Strong glow applied via inline style per dot colour */
  }}

  .dot-ring {{
    position: absolute;
    border-radius: 50%;
    top: 50%; left: 50%;
    transform: translate(-50%, -50%);
    animation: pulse-ring 1.2s ease-out infinite;
    pointer-events: none;
  }}

  @keyframes pulse-ring {{
    0%   {{ width: 18px; height: 18px; opacity: 1.0; }}
    100% {{ width: 56px; height: 56px; opacity: 0; }}
  }}

  .finding-dot:hover .dot-core {{ transform: scale(1.6); }}
  .finding-dot.paused .dot-ring {{ animation-play-state: paused; opacity: 0.4; }}

  /* ── Tooltip ─────────────────────────────────────────────────────────── */
  #tooltip {{
    position: fixed;
    z-index: 9999;
    max-width: 280px;
    background: #161b22;
    border: 1px solid #58a6ff;
    border-radius: 6px;
    padding: 10px 12px;
    font-size: 11px;
    line-height: 1.5;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.15s;
    box-shadow: 0 4px 24px rgba(0,0,0,0.6);
  }}
  #tooltip.visible {{ opacity: 1; }}
  #tooltip .tt-label {{
    font-weight: bold; font-size: 11px;
    margin-bottom: 5px; padding-bottom: 5px;
    border-bottom: 1px solid #30363d;
  }}
  #tooltip .tt-label.warn  {{ color: #FFD700; }}   /* YELLOW — calcified   */
  #tooltip .tt-label.alert {{ color: #FF4444; }}   /* RED    — soft lipid  */
  #tooltip .tt-label.ok    {{ color: #00C851; }}   /* GREEN  — reference   */
  #tooltip .tt-body {{ color: #c9d1d9; font-size: 10.5px; }}
  #tooltip .tt-pause {{
    margin-top: 6px; padding-top: 5px; border-top: 1px solid #30363d;
    color: #58a6ff; font-size: 10px;
  }}

  /* ── Caption bar ─────────────────────────────────────────────────────── */
  #caption {{
    background: #0d1117; border: 1px solid #30363d; border-top: none;
    padding: 5px 10px; font-size: 11px; min-height: 28px;
    display: flex; align-items: center; gap: 6px; color: #c9d1d9;
  }}
  #caption .dot-icon {{
    width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
  }}

  /* ── Controls bar ─────────────────────────────────────────────────────── */
  #controls {{
    display: flex; align-items: center; gap: 8px;
    padding: 6px 4px; flex-wrap: wrap;
  }}
  button {{
    background: #21262d; border: 1px solid #30363d; color: #e6edf3;
    padding: 4px 12px; font-size: 11px; font-family: inherit;
    cursor: pointer; border-radius: 3px; transition: background 0.1s;
  }}
  button:hover {{ background: #30363d; }}
  #play-btn {{ color: #58a6ff; border-color: #58a6ff; }}
  #slice-counter {{ font-size: 11px; color: #8b949e; margin-left: auto; }}

  input[type=range] {{
    -webkit-appearance: none; height: 4px;
    background: #30363d; border-radius: 2px; width: 80px;
  }}
  input[type=range]::-webkit-slider-thumb {{
    -webkit-appearance: none; width: 12px; height: 12px;
    border-radius: 50%; background: #58a6ff; cursor: pointer;
  }}
  label {{ font-size: 10px; color: #8b949e; }}

  /* ── Slice index panel ───────────────────────────────────────────────── */
  #side-col {{
    width: 140px; flex-shrink: 0;
    display: flex; flex-direction: column; gap: 4px;
  }}

  #side-hdr {{
    background: #1c2128; border: 1px solid #30363d;
    padding: 4px 8px; font-size: 10px; color: #8b949e;
    text-transform: uppercase; letter-spacing: 0.05em;
  }}

  .slice-btn {{
    background: #161b22; border: 1px solid #30363d;
    color: #8b949e; padding: 5px 8px; font-size: 10px;
    font-family: inherit; text-align: left; cursor: pointer;
    border-radius: 2px; transition: all 0.1s;
    display: flex; align-items: center; gap: 6px;
  }}
  .slice-btn:hover {{ background: #1c2128; color: #e6edf3; }}
  .slice-btn.active {{
    background: #0d2137; border-color: #58a6ff; color: #58a6ff;
  }}
  .slice-btn .s-dot {{
    width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  }}
  .slice-btn .s-uid {{ font-size: 9px; color: #8b949e; }}

  #series-box {{
    background: #161b22; border: 1px solid #30363d;
    padding: 6px 8px; margin-top: 4px;
  }}
  #series-box .sb-hdr {{
    font-size: 9px; color: #8b949e; margin-bottom: 4px;
    text-transform: uppercase; letter-spacing: 0.05em;
  }}
  #series-box .sb-uid {{ font-size: 9px; color: #c9d1d9; line-height: 1.6; }}
</style>
</head>
<body>

<div id="tooltip">
  <div class="tt-label" id="tt-label"></div>
  <div class="tt-body"  id="tt-body"></div>
  <div class="tt-pause">⏸ Paused — move mouse away to resume</div>
</div>

<div id="viewer-wrap">

  <!-- ── Main column ─────────────────────────────────────────────────── -->
  <div id="canvas-col">

    <div id="hdr">
      <span>⬛ NEXUS · SYNGO FASTVIEW SIMULATION</span>
      <span>NAEOTOM Alpha.Pro</span>
    </div>
    <div id="hdr" style="justify-content:flex-start; gap:20px;">
      <span><b>ZHANG, ZHIMING</b></span>
      <span>ID: 350063 · DOB: 14/03/1955 M · 47 bpm</span>
      <span style="margin-left:auto">Ref: Dr Thanneermalai Renganathan</span>
    </div>
    <div id="hdr">
      <span>Study: CHEART2 · 20/04/2026 15:10</span>
      <span>W: 400 / C: 40 · mAs 18</span>
    </div>

    <div style="background:#0d1117; border:1px solid #30363d; border-top:none;
                padding:5px 10px; display:flex; gap:20px; font-size:10.5px;
                color:#c9d1d9; align-items:center;">
      <span style="color:#8b949e; text-transform:uppercase;
                   letter-spacing:.06em; font-size:9px; flex-shrink:0;">
        DOT LEGEND
      </span>
      <span style="display:flex;align-items:center;gap:6px;">
        <span style="display:inline-block;width:13px;height:13px;
                     border-radius:50%;background:#FF4444;
                     box-shadow:0 0 8px #FF4444,0 0 16px #FF4444;
                     flex-shrink:0;"></span>
        <b style="color:#FF4444">RED</b>&nbsp;— Soft/lipid plaque · CRITICAL
      </span>
      <span style="display:flex;align-items:center;gap:6px;">
        <span style="display:inline-block;width:13px;height:13px;
                     border-radius:50%;background:#FFD700;
                     box-shadow:0 0 8px #FFD700,0 0 16px #FFD700;
                     flex-shrink:0;"></span>
        <b style="color:#FFD700">YELLOW</b>&nbsp;— Calcified plaque · MODERATE
      </span>
      <span style="display:flex;align-items:center;gap:6px;">
        <span style="display:inline-block;width:13px;height:13px;
                     border-radius:50%;background:#00C851;
                     box-shadow:0 0 8px #00C851,0 0 16px #00C851;
                     flex-shrink:0;"></span>
        <b style="color:#00C851">GREEN</b>&nbsp;— FAI measurement · REFERENCE
      </span>
      <span style="margin-left:auto;color:#8b949e;font-size:9px;flex-shrink:0;">
        Hover any dot to pause &amp; inspect
      </span>
    </div>

    <div id="canvas-wrap">
      <!-- Real DICOM background (hidden if no images) -->
      <img id="slice-img" src="" alt="" style="display:none"/>

      <!-- Synthetic SVG fallback -->
      <svg id="synthetic-svg" viewBox="0 0 400 400"
           xmlns="http://www.w3.org/2000/svg"></svg>

      <!-- Dot overlay container -->
      <div id="dot-layer" style="position:absolute;inset:0;"></div>

      <!-- Slice label overlay -->
      <div id="sl-overlay" style="
        position:absolute; top:8px; left:50%; transform:translateX(-50%);
        font-size:12px; color:#e6edf3; letter-spacing:0.1em; pointer-events:none;">
        SL 1
      </div>
      <div style="
        position:absolute; bottom:8px; right:8px;
        font-size:10px; color:#8b949e; pointer-events:none;">
        5cm
      </div>
      <div id="uid-overlay" style="
        position:absolute; bottom:8px; left:8px;
        font-size:9px; color:#8b949e; pointer-events:none;">
        UID: 77172526
      </div>
    </div>

    <!-- Caption -->
    <div id="caption">
      <div class="dot-icon" id="cap-dot" style="background:#FFD700;box-shadow:0 0 6px #FFD700;"></div>
      <span id="cap-text">Calcified plaque at LMCA ostium</span>
    </div>

    <!-- Controls -->
    <div id="controls">
      <button id="play-btn">⏸ PAUSE</button>
      <button onclick="prevSlice()">◀ PREV</button>
      <button onclick="nextSlice()">NEXT ▶</button>
      <label>Speed <input type="range" id="speed-slider"
             min="600" max="3000" step="200" value="1600"
             oninput="setSpeed(this.value)"></label>
      <span id="slice-counter">1 / 5</span>
    </div>

  </div><!-- /canvas-col -->

  <!-- ── Side panel ──────────────────────────────────────────────────── -->
  <div id="side-col">
    <div id="side-hdr">■ SLICE INDEX</div>
    <div id="slice-list"></div>

    <div id="series-box">
      <div class="sb-hdr">■ SERIES</div>
      <div class="sb-uid">Syngo slices:<br>
        77172526<br>77172537<br>77172548<br>77172559<br>77172570
      </div>
    </div>
  </div>

</div><!-- /viewer-wrap -->

<script>
// ── Data from Python ───────────────────────────────────────────────────────
const FINDINGS    = {findings_json};
const SLICE_LABELS= {labels_json};
const SLICE_IMGS  = {images_json};
const HAS_REAL    = SLICE_IMGS.some(x => x !== null);

// ── State ─────────────────────────────────────────────────────────────────
let currentSlice  = 0;
let playing       = true;
let hoveredDot    = null;
let intervalId    = null;
let speedMs       = 1600;

// ── Synthetic anatomy per slice ────────────────────────────────────────────
const SYNTHETIC = [
  // SL1 — LMCA
  `<ellipse cx="200" cy="200" rx="145" ry="155" fill="none" stroke="#444" stroke-width="2"/>
   <ellipse cx="195" cy="195" rx="80" ry="90" fill="#1a2030" stroke="#555" stroke-width="1.5"/>
   <circle cx="204" cy="192" r="28" fill="#1e2840" stroke="#888" stroke-width="1.5"/>
   <circle cx="240" cy="178" r="22" fill="#1e2840" stroke="#777" stroke-width="1"/>
   <ellipse cx="200" cy="310" rx="50" ry="38" fill="#1a1a2e" stroke="#444"/>
   <rect x="170" y="60" width="60" height="30" rx="4" fill="#2a3040" stroke="#555"/>`,
  // SL2 — pLAD
  `<ellipse cx="200" cy="200" rx="145" ry="155" fill="none" stroke="#444" stroke-width="2"/>
   <ellipse cx="193" cy="197" rx="82" ry="88" fill="#1a2030" stroke="#555" stroke-width="1.5"/>
   <circle cx="183" cy="176" r="30" fill="#1e2840" stroke="#888" stroke-width="1.5"/>
   <circle cx="238" cy="183" r="20" fill="#1e2840" stroke="#777"/>
   <ellipse cx="200" cy="312" rx="50" ry="36" fill="#1a1a2e" stroke="#444"/>
   <rect x="170" y="60" width="62" height="29" rx="4" fill="#2a3040" stroke="#555"/>`,
  // SL3 — mid LAD (the critical one)
  `<ellipse cx="200" cy="200" rx="143" ry="153" fill="none" stroke="#444" stroke-width="2"/>
   <ellipse cx="192" cy="200" rx="78" ry="86" fill="#1a2030" stroke="#555" stroke-width="1.5"/>
   <circle cx="184" cy="184" r="32" fill="#1e2840" stroke="#888" stroke-width="2"/>
   <circle cx="237" cy="186" r="21" fill="#1e2840" stroke="#777"/>
   <circle cx="184" cy="184" r="8" fill="#3a1010" stroke="#EF4444" stroke-width="1.5"/>
   <ellipse cx="198" cy="314" rx="48" ry="37" fill="#1a1a2e" stroke="#444"/>
   <rect x="169" y="60" width="63" height="30" rx="4" fill="#2a3040" stroke="#555"/>`,
  // SL4 — mRCA
  `<ellipse cx="200" cy="200" rx="144" ry="154" fill="none" stroke="#444" stroke-width="2"/>
   <ellipse cx="194" cy="202" rx="79" ry="87" fill="#1a2030" stroke="#555" stroke-width="1.5"/>
   <circle cx="220" cy="200" r="26" fill="#1e2840" stroke="#888" stroke-width="1.5"/>
   <circle cx="173" cy="186" r="18" fill="#1e2840" stroke="#777"/>
   <ellipse cx="200" cy="310" rx="50" ry="37" fill="#1a1a2e" stroke="#444"/>
   <rect x="169" y="61" width="62" height="29" rx="4" fill="#2a3040" stroke="#555"/>`,
  // SL5 — FAI zone
  `<ellipse cx="200" cy="200" rx="144" ry="153" fill="none" stroke="#444" stroke-width="2"/>
   <ellipse cx="196" cy="200" rx="76" ry="84" fill="#1a2030" stroke="#555" stroke-width="1.5"/>
   <circle cx="208" cy="208" r="27" fill="#1e2840" stroke="#888" stroke-width="1.5"/>
   <ellipse cx="186" cy="174" rx="28" ry="18" fill="#0a1f10" stroke="#00C851" stroke-width="1.5"
            stroke-dasharray="3,2" opacity="0.8"/>
   <ellipse cx="200" cy="312" rx="49" ry="36" fill="#1a1a2e" stroke="#444"/>
   <rect x="169" y="60" width="62" height="30" rx="4" fill="#2a3040" stroke="#555"/>`,
];

// ── Build slice index buttons ──────────────────────────────────────────────
const DOT_COLOURS = ["#FFD700","#FFD700","#FF4444","#FFD700","#00C851"];
const list = document.getElementById("slice-list");
SLICE_LABELS.forEach((uid, i) => {{
  const btn = document.createElement("button");
  btn.className = "slice-btn" + (i===0 ? " active" : "");
  btn.id = "sbtn-"+i;
  btn.innerHTML = `
    <div class="s-dot" style="background:${{DOT_COLOURS[i]}}"></div>
    <div><div>SL ${{i+1}}</div><div class="s-uid">${{uid}}</div></div>`;
  btn.onclick = () => goToSlice(i);
  list.appendChild(btn);
}});

// ── Tooltip ────────────────────────────────────────────────────────────────
const tooltip  = document.getElementById("tooltip");
const ttLabel  = document.getElementById("tt-label");
const ttBody   = document.getElementById("tt-body");

function showTooltip(finding, mouseX, mouseY) {{
  ttLabel.textContent = finding.label;
  ttLabel.className   = "tt-label " + finding.severity;
  ttBody.textContent  = finding.detail;
  // Position — keep inside viewport
  let tx = mouseX + 16, ty = mouseY - 20;
  if (tx + 290 > window.innerWidth)  tx = mouseX - 295;
  if (ty + 130 > window.innerHeight) ty = mouseY - 140;
  tooltip.style.left = tx + "px";
  tooltip.style.top  = ty + "px";
  tooltip.classList.add("visible");
}}
function hideTooltip() {{
  tooltip.classList.remove("visible");
}}

// ── Render a single slice ──────────────────────────────────────────────────
function renderSlice(idx) {{
  const img    = document.getElementById("slice-img");
  const svg    = document.getElementById("synthetic-svg");
  const layer  = document.getElementById("dot-layer");
  const slOvl  = document.getElementById("sl-overlay");
  const uidOvl = document.getElementById("uid-overlay");

  slOvl.textContent  = "SL " + (idx+1);
  uidOvl.textContent = "UID: " + SLICE_LABELS[idx];

  // Background: real image OR synthetic SVG
  if (SLICE_IMGS[idx]) {{
    img.src           = SLICE_IMGS[idx];
    img.style.display = "block";
    svg.style.display = "none";
  }} else {{
    img.style.display = "none";
    svg.style.display = "block";
    svg.innerHTML     = SYNTHETIC[idx];
  }}

  // Slice index sidebar
  document.querySelectorAll(".slice-btn").forEach((b,i) =>
    b.classList.toggle("active", i===idx));

  // Finding dots for this slice
  layer.innerHTML = "";
  FINDINGS.filter(f => f.slice === idx).forEach(f => {{
    const dot = document.createElement("div");
    dot.className   = "finding-dot";
    dot.style.left  = f.x + "%";
    dot.style.top   = f.y + "%";

    dot.innerHTML = `
      <div class="dot-ring" style="
        border: 2.5px solid ${{f.pulse}};
        box-shadow: 0 0 10px ${{f.pulse}}, 0 0 20px ${{f.colour}};"></div>
      <div class="dot-core" style="
        background:${{f.colour}};
        box-shadow: 0 0 10px ${{f.colour}}, 0 0 22px ${{f.colour}}, 0 0 4px #fff;"></div>`;

    // Hover — pause animation + show tooltip
    dot.addEventListener("mouseenter", e => {{
      hoveredDot = dot;
      dot.classList.add("paused");
      pausePlayback();
      showTooltip(f, e.clientX, e.clientY);
      updateCaption(f);
    }});
    dot.addEventListener("mousemove", e => {{
      showTooltip(f, e.clientX, e.clientY);
    }});
    dot.addEventListener("mouseleave", () => {{
      hoveredDot = null;
      dot.classList.remove("paused");
      hideTooltip();
      if (playing) resumePlayback();
    }});

    layer.appendChild(dot);
  }});

  // Caption for first finding on this slice
  const first = FINDINGS.find(f => f.slice === idx);
  if (first) updateCaption(first);

  document.getElementById("slice-counter").textContent =
    (idx+1) + " / " + SLICE_LABELS.length;
}}

function updateCaption(f) {{
  document.getElementById("cap-dot").style.background = f.colour;
  document.getElementById("cap-text").textContent =
    (f.severity === "alert" ? "■ " : "● ") + f.label.split("—")[1]?.trim() || f.label;
}}

// ── Navigation ─────────────────────────────────────────────────────────────
function goToSlice(idx) {{
  currentSlice = idx;
  renderSlice(idx);
}}
function nextSlice() {{
  currentSlice = (currentSlice + 1) % SLICE_LABELS.length;
  renderSlice(currentSlice);
}}
function prevSlice() {{
  currentSlice = (currentSlice - 1 + SLICE_LABELS.length) % SLICE_LABELS.length;
  renderSlice(currentSlice);
}}

// ── Playback ───────────────────────────────────────────────────────────────
function startAuto() {{
  if (intervalId) clearInterval(intervalId);
  intervalId = setInterval(() => {{
    if (!hoveredDot) nextSlice();  // skip advance while hovering
  }}, speedMs);
}}
function pausePlayback() {{
  if (intervalId) {{ clearInterval(intervalId); intervalId = null; }}
  document.getElementById("play-btn").textContent = "▶ PLAY";
}}
function resumePlayback() {{
  startAuto();
  document.getElementById("play-btn").textContent = "⏸ PAUSE";
}}
function setSpeed(v) {{
  speedMs = parseInt(v);
  if (playing && !hoveredDot) {{ startAuto(); }}
}}

document.getElementById("play-btn").onclick = () => {{
  playing = !playing;
  if (playing) resumePlayback();
  else         pausePlayback();
  document.getElementById("play-btn").textContent =
    playing ? "⏸ PAUSE" : "▶ PLAY";
}};

// ── Init ───────────────────────────────────────────────────────────────────
renderSlice(0);
startAuto();
</script>
</body>
</html>
"""

    components.html(html, height=680, scrolling=False)


# ── Streamlit page entry point ────────────────────────────────────────────────
if __name__ == "__main__" or True:
    st.set_page_config(layout="wide", page_title="HERMES Imaging")
    render_viewer()
