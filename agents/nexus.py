"""
agents/nexus.py
NEXUS — Digital Twin & Population Simulation Agent.
AGENTS.md Section 4.
"""

from core.gemini import gemini_chat
from core.session import add_log

NEXUS_SYSTEM_PROMPT = """You are NEXUS, the Population Health Digital Twin agent.
You specialise in: population-level health simulation, disease cluster detection,
intervention impact modelling, and 5-year cohort trajectory analysis.
Use epidemiological reasoning and population health frameworks."""

OFFLINE = (
    "🔗 **[NEXUS]** Simulating population health digital twin...\n\n"
    "✅ 1,240 patient cohort evaluated across 8 Australian regions\n"
    "⚠️ 247 patients in Obese I–III range (BMI ≥30) — high cardiovascular risk\n"
    "⚠️ 3 critical disease clusters detected (T2DM + hypertension + obesity)\n"
    "📋 Projected 5-year CVD event rate: 14.2% without intervention\n"
    "📋 With weight management programme: projected 8.7% (↓ 38.7%)\n"
    "✅ Population stable under current intervention programmes\n\n"
    "_Connect live API for real execution._"
)

# ---------------------------------------------------------------------------
# CTCA Slice simulation data — Syngo FastView series
# Slice UIDs correspond to the problematic CTCA series for ZHANG,ZHIMING
# ---------------------------------------------------------------------------
CTCA_SLICES = [
    {
        "uid": "77172526",
        "sl": 1,
        "label": "SL 1 — Aortic root / LMCA origin",
        "finding": "⚠️ Calcified plaque at LMCA ostium",
        "severity": "moderate",
    },
    {
        "uid": "77172537",
        "sl": 2,
        "label": "SL 2 — Proximal LAD",
        "finding": "⚠️ Mixed plaque, proximal LAD — 40–50% stenosis",
        "severity": "moderate",
    },
    {
        "uid": "77172548",
        "sl": 3,
        "label": "SL 3 — Mid LAD / RCA",
        "finding": "🔴 Significant non-calcified plaque, mid LAD — 60–70% stenosis",
        "severity": "critical",
    },
    {
        "uid": "77172559",
        "sl": 4,
        "label": "SL 4 — Distal LAD / Cx",
        "finding": "⚠️ Mild calcification, Cx marginal branch",
        "severity": "mild",
    },
    {
        "uid": "77172570",
        "sl": 5,
        "label": "SL 5 — RCA mid-distal",
        "finding": "⚠️ Calcified plaque RCA, 30–40% stenosis",
        "severity": "moderate",
    },
]

CTCA_METADATA = {
    "patient":   "ZHANG, ZHIMING",
    "dob":       "14/03/1955  M",
    "id":        "350063",
    "study":     "CHEART2 — Coronary CTA",
    "date":      "20/04/2026  15:10:21",
    "scanner":   "NAEOTOM Alpha.Pro (Siemens)",
    "facility":  "Medscan Merrylands",
    "ref":       "Dr Thanneermalai Renganathan",
    "protocol":  "47 bpm · 70% D · 66 ms · ME_70keV",
    "window":    "W: 400 / C: 40",
    "mAs":       "18",
}

CTCA_VIEWER_HTML = """
<div id="nexus-ctca-root" style="
    font-family: 'Courier New', monospace;
    background: #000;
    color: #d0e8ff;
    border: 1px solid #1a4a7a;
    border-radius: 6px;
    padding: 0;
    max-width: 860px;
    box-shadow: 0 0 24px #0a2a4a;
    user-select: none;
">

<!-- Title bar -->
<div style="
    background: linear-gradient(90deg, #0d2b4a 0%, #1a4a8a 100%);
    padding: 6px 12px;
    display: flex;
    align-items: center;
    gap: 10px;
    border-radius: 6px 6px 0 0;
    border-bottom: 1px solid #1a4a7a;
">
  <span style="font-size:11px; color:#7bb8f0; letter-spacing:2px;">▣ NEXUS · SYNGO FASTVIEW SIMULATION</span>
  <span style="margin-left:auto; font-size:10px; color:#4a88c0;">NAEOTOM Alpha.Pro</span>
</div>

<!-- Patient banner -->
<div style="
    display: flex;
    justify-content: space-between;
    padding: 6px 14px;
    background: #020e1a;
    font-size: 10.5px;
    border-bottom: 1px solid #0d2b4a;
    flex-wrap: wrap;
    gap: 6px;
">
  <div>
    <div style="color:#fff; font-weight:bold; font-size:12px;">ZHANG, ZHIMING</div>
    <div style="color:#7bb8f0;">ID: 350063 &nbsp;·&nbsp; DOB: 14/03/1955 M &nbsp;·&nbsp; 47 bpm</div>
    <div style="color:#7bb8f0;">Study: CHEART2 &nbsp;·&nbsp; 20/04/2026 15:10</div>
  </div>
  <div style="text-align:right;">
    <div style="color:#aad4ff;">Medscan Merrylands</div>
    <div style="color:#7bb8f0;">Ref: Dr Thanneermalai Renganathan</div>
    <div style="color:#7bb8f0;">W: 400 / C: 40 &nbsp;·&nbsp; mAs 18</div>
  </div>
</div>

<!-- Main viewer area -->
<div style="display:flex;">

  <!-- CT canvas -->
  <div style="flex:1; position:relative; background:#000; min-height:420px; overflow:hidden;">
    <canvas id="nexus-ct-canvas" width="680" height="420"
      style="display:block; width:100%; height:420px;"></canvas>

    <!-- Overlay labels -->
    <div style="position:absolute; top:8px; left:12px; font-size:11px; color:#d0e8ff;">R</div>
    <div id="nexus-slice-label" style="
        position:absolute; top:8px; left:50%;
        transform:translateX(-50%);
        font-size:11px; color:#aad4ff; letter-spacing:1px;
    ">SL 1</div>
    <div style="position:absolute; top:8px; right:12px; font-size:11px; color:#d0e8ff;">A</div>

    <!-- Scale bar -->
    <div style="position:absolute; bottom:36px; right:14px; font-size:10px; color:#7bb8f0;">5cm</div>
    <div style="position:absolute; bottom:28px; right:14px; width:60px; height:2px;
                background: linear-gradient(90deg, transparent 0%, #7bb8f0 40%, #7bb8f0 60%, transparent 100%);"></div>

    <!-- Finding badge -->
    <div id="nexus-finding" style="
        position:absolute; bottom:8px; left:8px; right:80px;
        background: rgba(0,20,60,0.85);
        border: 1px solid #1a4a7a;
        border-radius: 4px;
        padding: 4px 10px;
        font-size:10.5px;
        color:#ffd080;
        transition: opacity 0.4s;
    ">⚠️ Calcified plaque at LMCA ostium</div>

    <!-- UID watermark -->
    <div id="nexus-uid" style="
        position:absolute; bottom:8px; right:8px;
        font-size:9px; color:#2a5a9a;
    ">UID: 77172526</div>

    <!-- Play overlay when paused -->
    <div id="nexus-paused-overlay" style="
        display:none;
        position:absolute; inset:0;
        background:rgba(0,0,0,0.35);
        align-items:center; justify-content:center;
    ">
      <div style="font-size:48px; color:rgba(255,255,255,0.6);">⏸</div>
    </div>
  </div>

  <!-- Right panel -->
  <div style="
    width:160px;
    background:#020e1a;
    border-left: 1px solid #0d2b4a;
    padding: 10px 8px;
    font-size:10px;
    color:#7bb8f0;
    display:flex; flex-direction:column; gap:8px;
  ">
    <div style="color:#aad4ff; font-weight:bold; font-size:10.5px; letter-spacing:1px;">
      ▣ SLICE INDEX
    </div>
    <div id="nexus-slice-list" style="display:flex; flex-direction:column; gap:4px;">
    </div>

    <div style="margin-top:auto; border-top:1px solid #0d2b4a; padding-top:8px;">
      <div style="color:#aad4ff; margin-bottom:4px; font-size:10px; letter-spacing:1px;">■ SERIES</div>
      <div style="color:#4a88c0;">Syngo slices:</div>
      <div style="color:#2a5878; font-size:9px; line-height:1.6;">
        77172526<br>77172537<br>77172548<br>77172559<br>77172570
      </div>
    </div>
  </div>
</div>

<!-- Controls bar -->
<div style="
    background:#020e1a;
    border-top:1px solid #0d2b4a;
    padding: 8px 14px;
    display:flex; align-items:center; gap:10px;
    border-radius: 0 0 6px 6px;
">
  <button id="nexus-btn-play" onclick="nexusCTCA.togglePlay()" style="
    background:#0d2b4a; border:1px solid #1a4a7a; color:#7bb8f0;
    padding:4px 14px; border-radius:3px; cursor:pointer; font-size:11px;
    font-family: 'Courier New', monospace;
  ">⏸ PAUSE</button>

  <button onclick="nexusCTCA.stepBy(-1)" style="
    background:#0d2b4a; border:1px solid #1a4a7a; color:#7bb8f0;
    padding:4px 10px; border-radius:3px; cursor:pointer; font-size:11px;
    font-family: 'Courier New', monospace;
  ">◀ PREV</button>

  <button onclick="nexusCTCA.stepBy(1)" style="
    background:#0d2b4a; border:1px solid #1a4a7a; color:#7bb8f0;
    padding:4px 10px; border-radius:3px; cursor:pointer; font-size:11px;
    font-family: 'Courier New', monospace;
  ">NEXT ▶</button>

  <!-- Speed control -->
  <label style="font-size:10px; color:#4a88c0; margin-left:auto;">Speed</label>
  <input id="nexus-speed" type="range" min="500" max="3000" step="250" value="1500"
    oninput="nexusCTCA.setSpeed(this.value)"
    style="width:70px; accent-color:#1a6aaa;">

  <span id="nexus-frame-counter" style="font-size:10px; color:#4a88c0; min-width:40px; text-align:right;">
    1 / 5
  </span>
</div>

<!-- Not for diagnostic use -->
<div style="text-align:center; font-size:9px; color:#2a4a6a; padding:3px;">
  ★ NEXUS SIMULATION — Not intended for diagnostic use ★
</div>

</div>

<script>
(function() {

// ── Slice data ──────────────────────────────────────────────────────────────
const SLICES = [
  { uid:"77172526", sl:"SL 1", label:"SL 1 — Aortic root / LMCA origin",
    finding:"⚠️ Calcified plaque at LMCA ostium", severity:"moderate",
    sp: -1918.25 },
  { uid:"77172537", sl:"SL 2", label:"SL 2 — Proximal LAD",
    finding:"⚠️ Mixed plaque, proximal LAD — 40–50% stenosis", severity:"moderate",
    sp: -1916.50 },
  { uid:"77172548", sl:"SL 3", label:"SL 3 — Mid LAD / RCA",
    finding:"🔴 Significant non-calcified plaque, mid LAD — 60–70% stenosis", severity:"critical",
    sp: -1915.25 },
  { uid:"77172559", sl:"SL 4", label:"SL 4 — Distal LAD / Cx",
    finding:"⚠️ Mild calcification, Cx marginal branch", severity:"mild",
    sp: -1913.00 },
  { uid:"77172570", sl:"SL 5", label:"SL 5 — RCA mid-distal",
    finding:"⚠️ Calcified plaque RCA, 30–40% stenosis", severity:"moderate",
    sp: -1911.75 },
];

// ── Canvas renderer ─────────────────────────────────────────────────────────
const canvas = document.getElementById('nexus-ct-canvas');
const ctx    = canvas.getContext('2d');

// Seeded pseudo-random for stable noise between frames
function seededRand(seed) {
  let s = seed;
  return function() {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

// Draw a simulated CT cardiac slice
function drawSlice(idx) {
  const W = canvas.width, H = canvas.height;
  const sl = SLICES[idx];
  const rng = seededRand(idx * 7919 + 1);

  // Background
  ctx.fillStyle = '#000';
  ctx.fillRect(0, 0, W, H);

  // Chest wall arc
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(W/2, -60, 320, 300, 0, 0, Math.PI);
  ctx.strokeStyle = '#c8c8c8';
  ctx.lineWidth = 18;
  ctx.stroke();
  ctx.restore();

  // Sternum / anterior structure
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(W/2 - 28, 28, 56, 32, 6);
  ctx.fillStyle = '#e0e0e0';
  ctx.fill();
  ctx.restore();

  // Pericardial sac outline
  ctx.save();
  ctx.beginPath();
  const hx = W/2 - 20, hy = H/2 - 30;
  ctx.ellipse(hx, hy, 170, 155, -0.15, 0, Math.PI*2);
  ctx.strokeStyle = 'rgba(150,180,200,0.35)';
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();

  // Heart mass — main grey blob
  ctx.save();
  const grad = ctx.createRadialGradient(hx, hy, 20, hx, hy, 160);
  grad.addColorStop(0,   'rgba(120,130,140,0.95)');
  grad.addColorStop(0.5, 'rgba(90,100,110,0.88)');
  grad.addColorStop(1,   'rgba(40,50,60,0.0)');
  ctx.beginPath();
  ctx.ellipse(hx, hy, 160, 150, -0.15, 0, Math.PI*2);
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.restore();

  // Right ventricle — left side (patient right)
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(hx - 55, hy - 10, 80, 70, 0.2, 0, Math.PI*2);
  ctx.fillStyle = 'rgba(70,80,90,0.85)';
  ctx.fill();
  ctx.restore();

  // Left ventricle — denser, rounder
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(hx + 50, hy + 20, 68, 72, -0.1, 0, Math.PI*2);
  ctx.fillStyle = 'rgba(85,95,105,0.90)';
  ctx.fill();
  // Myocardium ring
  ctx.strokeStyle = 'rgba(160,170,180,0.55)';
  ctx.lineWidth = 6;
  ctx.stroke();
  ctx.restore();

  // Aorta (right anterior)
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(hx + 80, hy - 80, 28, 28, 0, 0, Math.PI*2);
  ctx.fillStyle = 'rgba(200,210,220,0.80)';
  ctx.fill();
  ctx.strokeStyle = '#bbb';
  ctx.lineWidth = 3;
  ctx.stroke();
  ctx.restore();

  // Pulmonary artery
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(hx + 10, hy - 90, 22, 20, 0.3, 0, Math.PI*2);
  ctx.fillStyle = 'rgba(170,185,200,0.70)';
  ctx.fill();
  ctx.restore();

  // Descending aorta (posterior-left)
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(hx - 130, hy + 60, 22, 22, 0, 0, Math.PI*2);
  ctx.fillStyle = 'rgba(190,200,215,0.80)';
  ctx.fill();
  ctx.strokeStyle = '#aaa';
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.restore();

  // Spine (posterior)
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(W/2 + 50, H - 60, 32, 28, 0, 0, Math.PI*2);
  ctx.fillStyle = '#d8d8d8';
  ctx.fill();
  ctx.restore();

  // Esophagus (small oval near spine)
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(W/2 + 10, H - 72, 10, 12, 0, 0, Math.PI*2);
  ctx.fillStyle = 'rgba(80,80,80,0.7)';
  ctx.fill();
  ctx.restore();

  // Lungs — black air regions
  // Right lung (patient's right = image left)
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(W/2 - 200, H/2 + 10, 90, 130, 0.2, 0, Math.PI*2);
  ctx.fillStyle = 'rgba(5,5,5,0.95)';
  ctx.fill();
  ctx.restore();
  // Left lung
  ctx.save();
  ctx.beginPath();
  ctx.ellipse(W/2 + 230, H/2 + 20, 70, 120, -0.15, 0, Math.PI*2);
  ctx.fillStyle = 'rgba(5,5,5,0.95)';
  ctx.fill();
  ctx.restore();

  // ── Severity-dependent plaque overlays ──────────────────────────────────
  function drawCalcPlaque(x, y, r, alpha) {
    ctx.save();
    const pg = ctx.createRadialGradient(x, y, 0, x, y, r);
    pg.addColorStop(0,   `rgba(255,255,240,${alpha})`);
    pg.addColorStop(0.6, `rgba(220,220,200,${alpha*0.7})`);
    pg.addColorStop(1,   'rgba(200,200,180,0)');
    ctx.beginPath();
    ctx.ellipse(x, y, r, r*0.75, rng()*Math.PI, 0, Math.PI*2);
    ctx.fillStyle = pg;
    ctx.fill();
    ctx.restore();
  }

  function drawSoftPlaque(x, y, r, alpha) {
    ctx.save();
    const sg = ctx.createRadialGradient(x, y, 0, x, y, r);
    sg.addColorStop(0,   `rgba(100,120,80,${alpha})`);
    sg.addColorStop(0.7, `rgba(80,100,60,${alpha*0.5})`);
    sg.addColorStop(1,   'rgba(60,80,40,0)');
    ctx.beginPath();
    ctx.ellipse(x, y, r, r*0.8, rng()*Math.PI, 0, Math.PI*2);
    ctx.fillStyle = sg;
    ctx.fill();
    ctx.restore();
  }

  if (sl.severity === 'critical') {
    // Large mixed plaque, mid LAD
    drawSoftPlaque(hx - 20, hy - 50, 22, 0.85);
    drawCalcPlaque(hx - 14, hy - 46, 8, 0.90);
    // Stenosis indicator ring
    ctx.save();
    ctx.beginPath();
    ctx.arc(hx - 20, hy - 50, 24, 0, Math.PI*2);
    ctx.strokeStyle = 'rgba(255,80,80,0.55)';
    ctx.lineWidth = 2;
    ctx.setLineDash([4,3]);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();
  } else if (sl.severity === 'moderate') {
    drawCalcPlaque(hx + 62, hy - 92, 10, 0.85);
    drawCalcPlaque(hx + 58, hy - 88, 6, 0.75);
  } else {
    drawCalcPlaque(hx + 30, hy + 40, 6, 0.65);
  }

  // ── CT noise texture ────────────────────────────────────────────────────
  const imgData = ctx.getImageData(0, 0, W, H);
  const d = imgData.data;
  const nr = seededRand(idx * 3141 + 59);
  for (let i = 0; i < d.length; i += 4) {
    const n = (nr() - 0.5) * 18;
    d[i]   = Math.min(255, Math.max(0, d[i]   + n));
    d[i+1] = Math.min(255, Math.max(0, d[i+1] + n));
    d[i+2] = Math.min(255, Math.max(0, d[i+2] + n));
  }
  ctx.putImageData(imgData, 0, 0);

  // ── Scan-line overlay ───────────────────────────────────────────────────
  for (let y = 0; y < H; y += 4) {
    ctx.fillStyle = 'rgba(0,0,0,0.06)';
    ctx.fillRect(0, y, W, 1);
  }
}

// ── Build slice index list ──────────────────────────────────────────────────
const listEl = document.getElementById('nexus-slice-list');
SLICES.forEach((s, i) => {
  const el = document.createElement('div');
  el.id = 'nexus-sl-item-' + i;
  el.style.cssText = `
    padding: 3px 6px;
    border-radius: 3px;
    cursor: pointer;
    font-size: 9.5px;
    border: 1px solid transparent;
    transition: all 0.2s;
  `;
  const dot = s.severity === 'critical' ? '🔴' : '⚠️';
  el.innerHTML = `<span style="color:#4a88c0;">${dot} ${s.sl}</span>
    <div style="color:#2a5878; font-size:8.5px; line-height:1.3;">${s.uid}</div>`;
  el.onclick = () => nexusCTCA.jumpTo(i);
  listEl.appendChild(el);
});

// ── Controller ──────────────────────────────────────────────────────────────
let current  = 0;
let playing  = true;
let interval = null;
let speed    = 1500;

function updateUI(idx) {
  const sl = SLICES[idx];

  // Draw
  drawSlice(idx);

  // Labels
  document.getElementById('nexus-slice-label').textContent = sl.sl;
  document.getElementById('nexus-uid').textContent = 'UID: ' + sl.uid;
  document.getElementById('nexus-frame-counter').textContent = (idx+1) + ' / ' + SLICES.length;

  // Finding
  const fEl = document.getElementById('nexus-finding');
  fEl.textContent = sl.finding;
  fEl.style.borderColor = sl.severity === 'critical' ? '#aa2222' :
                          sl.severity === 'moderate' ? '#aa8800' : '#226622';
  fEl.style.color = sl.severity === 'critical' ? '#ff8080' :
                    sl.severity === 'moderate' ? '#ffd080' : '#80ff80';

  // Sidebar highlight
  SLICES.forEach((_, i) => {
    const el = document.getElementById('nexus-sl-item-' + i);
    if (!el) return;
    el.style.background = i === idx ? '#0d2b4a' : 'transparent';
    el.style.borderColor = i === idx ? '#1a4a7a' : 'transparent';
  });
}

function tick() {
  current = (current + 1) % SLICES.length;
  updateUI(current);
}

function startLoop() {
  if (interval) clearInterval(interval);
  interval = setInterval(tick, speed);
}

window.nexusCTCA = {
  togglePlay() {
    playing = !playing;
    const btn = document.getElementById('nexus-btn-play');
    const ov  = document.getElementById('nexus-paused-overlay');
    if (playing) {
      startLoop();
      btn.textContent = '⏸ PAUSE';
      ov.style.display = 'none';
    } else {
      clearInterval(interval);
      btn.textContent = '▶ PLAY';
      ov.style.display = 'flex';
    }
  },
  stepBy(delta) {
    if (playing) this.togglePlay();
    current = (current + delta + SLICES.length) % SLICES.length;
    updateUI(current);
  },
  jumpTo(idx) {
    if (playing) this.togglePlay();
    current = idx;
    updateUI(current);
  },
  setSpeed(val) {
    speed = parseInt(val);
    if (playing) startLoop();
  }
};

// Init
updateUI(0);
startLoop();

})();
</script>
"""


N1_CONTINGENCY_OFFLINE = (
    "🔗 **[NEXUS]** Simulating N-1 contingency analysis...\n\n"
    "✅ 47 network nodes evaluated\n"
    "⚠️ 3 critical contingencies detected\n"
    "✅ System stable under N-1 conditions\n\n"
    "_Connect live API for real execution._"
)

N1_CTCA_PREAMBLE = """
🔗 **[NEXUS]** N-1 Digital Twin Simulation — Patient: ZHANG, ZHIMING (ID: 350063)

**Coronary CTA Analysis · Medscan Merrylands · 20/04/2026**

Simulating Syngo FastView series for problematic CTCA slices:
`77172526 → 77172537 → 77172548 → 77172559 → 77172570`

| Slice UID  | Region                  | Finding                                      | Severity |
|------------|-------------------------|----------------------------------------------|----------|
| 77172526   | Aortic root / LMCA      | Calcified plaque at LMCA ostium              | Moderate |
| 77172537   | Proximal LAD            | Mixed plaque — 40–50% stenosis               | Moderate |
| **77172548** | **Mid LAD / RCA**     | **Non-calcified plaque — 60–70% stenosis**   | **Critical** |
| 77172559   | Distal LAD / Cx         | Mild calcification, Cx marginal branch       | Mild     |
| 77172570   | RCA mid-distal          | Calcified plaque — 30–40% stenosis           | Moderate |

> 🔴 **Critical finding:** Slice 77172548 (SL 3) — Significant non-calcified vulnerable plaque,
> mid LAD. Estimated 60–70% stenosis. Recommend urgent cardiology review.

---
**▼ Interactive CTCA Slice Viewer (Syngo Simulation)**
"""


class NexusAgent:
    name = "NEXUS"
    icon = "🔗"
    role = "Digital Twin & Population Simulation"

    TRIGGER_COMMANDS = [
        "Run population health digital twin simulation on default cohort",
        "Run N-1 digital twin simulation on default network",
    ]

    def run(self, command: str) -> str:
        add_log(f"NEXUS:{command[:50]}")

        # ── N-1 / imaging branch ────────────────────────────────────────────
        cmd_lower = command.lower()
        if "n-1" in cmd_lower or "n1" in cmd_lower or "network" in cmd_lower:
            return self._run_n1_ctca()

        # ── Standard population simulation ─────────────────────────────────
        return gemini_chat(
            prompt=command,
            system_prompt=NEXUS_SYSTEM_PROMPT,
            offline_fallback=OFFLINE,
        )

    def _run_n1_ctca(self) -> str:
        """Return the markdown preamble + embedded HTML CTCA viewer."""
        return N1_CTCA_PREAMBLE + CTCA_VIEWER_HTML


# ── Registry ─────────────────────────────────────────────────────────────────
AGENT_REGISTRY = {
    "NEXUS": NexusAgent
}
