"""
pages/ctca_panel_viewer.py -- CTCA Multi-Panel Radiologist View
===============================================================
Standalone page: 5-panel grid (like fastView browser) with:
  - Fixed coloured annotation dots on each slice
  - Toggle to animated dot-pulse mode
  - SIMULATION ONLY watermark
  - Completely independent of existing chat.py viewer

Added to PAGES list in core/config.py by deploy script.
DO NOT modify pages/chat.py or any existing files.
"""

import streamlit as st
import streamlit.components.v1 as components
from auth.session import require_auth, render_user_sidebar

def render():
    user = require_auth()
    render_user_sidebar()

    st.markdown("""
        <style>
        .ctca-header {
            font-family: 'Courier New', monospace;
            color: #7bb8f0;
            font-size: 13px;
            letter-spacing: 3px;
            padding: 8px 0 4px 0;
            border-bottom: 1px solid #1a4a7a;
            margin-bottom: 12px;
        }
        .sim-badge {
            display: inline-block;
            background: rgba(180,0,0,0.85);
            color: #fff;
            font-family: 'Courier New', monospace;
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 2px;
            padding: 2px 10px;
            border-radius: 3px;
            margin-left: 16px;
            vertical-align: middle;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown(
        '<div class="ctca-header">&#9632; NEXUS &middot; CTCA MULTI-PANEL RADIOLOGIST VIEW'
        '<span class="sim-badge">SIMULATION ONLY</span></div>',
        unsafe_allow_html=True
    )

    # Controls row
    col1, col2, col3 = st.columns([2, 2, 4])
    with col1:
        animate = st.toggle("Animate finding dots", value=False)
    with col2:
        show_labels = st.toggle("Show slice labels", value=True)
    with col3:
        st.caption("Patient: ZHANG, ZHIMING &middot; ID 350063 &middot; 20/04/2026 &middot; Medscan Merrylands &middot; W:400 C:40")

    # Build the HTML panel
    html = _build_panel_html(animate=animate, show_labels=show_labels)
    components.html(html, height=820, scrolling=False)

    st.divider()
    st.caption(
        "**Annotation key:** "
        "[CRITICAL] 60-70% stenosis, non-calcified vulnerable plaque &nbsp;|&nbsp; "
        "[MODERATE] mixed/calcified plaque 30-50% &nbsp;|&nbsp; "
        "[MILD] minor calcification &nbsp;&nbsp; "
        "**NOT FOR DIAGNOSTIC USE -- SIMULATION ONLY**"
    )


def _build_panel_html(animate: bool, show_labels: bool) -> str:
    """Returns the complete self-contained HTML for the 5-panel grid."""

    anim_css = """
    @keyframes dotPulse {
        0%   { transform: translate(-50%,-50%) scale(1);   opacity: 1; }
        50%  { transform: translate(-50%,-50%) scale(1.8); opacity: 0.5; }
        100% { transform: translate(-50%,-50%) scale(1);   opacity: 1; }
    }
    @keyframes ringExpand {
        0%   { transform: translate(-50%,-50%) scale(0.8); opacity: 0.8; }
        100% { transform: translate(-50%,-50%) scale(2.4); opacity: 0; }
    }
    """ if animate else ""

    dot_anim_style = "animation: dotPulse 1.4s ease-in-out infinite;" if animate else ""
    ring_display   = "display:block;" if animate else "display:none;"

    label_display = "block" if show_labels else "none"

    # Slice definitions: uid, label, region, finding, severity, dot(x%,y%), colour
    slices = [
        {
            "uid": "77172526", "sl": "SL 1",
            "region": "Aortic root / LMCA",
            "finding": "Calcified plaque at LMCA ostium",
            "severity": "moderate",
            "dots": [{"x": 52, "y": 38, "color": "#f5c842", "label": "LMCA"}],
            "sp": -1918.25,
        },
        {
            "uid": "77172537", "sl": "SL 2",
            "region": "Proximal LAD",
            "finding": "Mixed plaque 40-50% stenosis",
            "severity": "moderate",
            "dots": [{"x": 55, "y": 35, "color": "#f5c842", "label": "pLAD"}],
            "sp": -1916.50,
        },
        {
            "uid": "77172548", "sl": "SL 3",
            "region": "Mid LAD / RCA",
            "finding": "Non-calcified plaque 60-70% stenosis CRITICAL",
            "severity": "critical",
            "dots": [
                {"x": 48, "y": 40, "color": "#ff4444", "label": "mLAD"},
                {"x": 58, "y": 52, "color": "#ff8800", "label": "RCA"},
            ],
            "sp": -1915.25,
        },
        {
            "uid": "77172559", "sl": "SL 4",
            "region": "Distal LAD / Cx",
            "finding": "Mild calcification Cx marginal",
            "severity": "mild",
            "dots": [{"x": 60, "y": 58, "color": "#44dd44", "label": "Cx"}],
            "sp": -1913.00,
        },
        {
            "uid": "77172570", "sl": "SL 5",
            "region": "RCA mid-distal",
            "finding": "Calcified plaque RCA 30-40% stenosis",
            "severity": "moderate",
            "dots": [{"x": 62, "y": 55, "color": "#f5c842", "label": "mRCA"}],
            "sp": -1911.75,
        },
    ]

    severity_border = {"critical": "#aa2222", "moderate": "#aa8800", "mild": "#226622"}
    severity_badge  = {"critical": "#ff4444", "moderate": "#f5c842", "mild": "#44dd44"}

    panels_html = ""
    for i, sl in enumerate(slices):
        border_col = severity_border[sl["severity"]]
        badge_col  = severity_badge[sl["severity"]]

        # Build dot HTML
        dots_html = ""
        for dot in sl["dots"]:
            dots_html += f"""
            <div style="
                position:absolute;
                left:{dot['x']}%; top:{dot['y']}%;
                transform:translate(-50%,-50%);
                z-index:10;
                pointer-events:none;
            ">
                <!-- Expanding ring (animate mode) -->
                <div style="
                    position:absolute; left:50%; top:50%;
                    width:28px; height:28px;
                    border:2px solid {dot['color']};
                    border-radius:50%;
                    {ring_display}
                    animation: ringExpand 1.4s ease-out infinite;
                "></div>
                <!-- Main dot -->
                <div style="
                    position:absolute; left:50%; top:50%;
                    transform:translate(-50%,-50%);
                    width:12px; height:12px;
                    background:{dot['color']};
                    border-radius:50%;
                    border:2px solid #fff;
                    box-shadow: 0 0 6px {dot['color']};
                    {dot_anim_style}
                "></div>
                <!-- Label -->
                <div style="
                    position:absolute; left:50%; top:calc(50% + 10px);
                    transform:translateX(-50%);
                    background:rgba(0,0,0,0.75);
                    color:{dot['color']};
                    font-family:'Courier New',monospace;
                    font-size:8px; font-weight:bold;
                    padding:1px 4px; border-radius:2px;
                    white-space:nowrap;
                    display:{label_display};
                ">{dot['label']}</div>
            </div>
            """

        # Canvas drawing script ID per panel
        cid = f"c{i}"

        panel_html = f"""
        <div style="
            position:relative;
            background:#000;
            border:2px solid {border_col};
            border-radius:4px;
            overflow:hidden;
            cursor:pointer;
        " onclick="nexusPanel.selectSlice({i})" id="panel-{i}">
            <!-- Canvas -->
            <canvas id="{cid}" width="260" height="220"
                    style="display:block; width:100%; height:220px;"></canvas>
            <!-- Annotation dots -->
            {dots_html}
            <!-- Top label -->
            <div style="
                position:absolute; top:4px; left:6px;
                font-family:'Courier New',monospace;
                font-size:9px; color:#aad4ff;
                background:rgba(0,0,0,0.6); padding:1px 5px; border-radius:2px;
                display:{label_display};
            ">{sl['sl']} &nbsp; {sl['uid']}</div>
            <!-- SP label -->
            <div style="
                position:absolute; top:4px; right:6px;
                font-family:'Courier New',monospace;
                font-size:8px; color:#4a88c0;
                background:rgba(0,0,0,0.6); padding:1px 4px; border-radius:2px;
            ">SP {sl['sp']}</div>
            <!-- Finding badge -->
            <div style="
                position:absolute; bottom:0; left:0; right:0;
                background:rgba(0,10,30,0.88);
                border-top:1px solid {border_col};
                font-family:'Courier New',monospace;
                font-size:8px; color:{badge_col};
                padding:3px 6px;
                white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
            ">{sl['finding']}</div>
        </div>
        """
        panels_html += panel_html

    # Selected slice detail panel (SL3 default)
    detail_html = """
    <div id="detail-panel" style="
        background:#020e1a;
        border:1px solid #1a4a7a;
        border-radius:4px;
        padding:10px 14px;
        font-family:'Courier New',monospace;
        font-size:10px;
        color:#7bb8f0;
        margin-top:10px;
    ">
        <span style="color:#aad4ff; font-weight:bold;">Selected: </span>
        <span id="detail-text">Click a panel to see details</span>
    </div>
    """

    slice_data_js = str([
        {
            "uid": sl["uid"], "sl": sl["sl"],
            "region": sl["region"], "finding": sl["finding"],
            "severity": sl["severity"], "sp": sl["sp"]
        }
        for sl in slices
    ]).replace("'", '"').replace("True","true").replace("False","false")

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
* {{ box-sizing: border-box; margin:0; padding:0; }}
body {{ background:#000; font-family:'Courier New',monospace; }}
{anim_css}
#grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    padding: 8px;
    background: #000;
}}
/* Highlight selected panel */
.panel-selected {{
    outline: 2px solid #7bb8f0 !important;
    outline-offset: -2px;
}}
</style>
</head>
<body>
<!-- Patient banner -->
<div style="
    background:#020e1a; padding:5px 12px;
    border-bottom:1px solid #0d2b4a;
    font-size:9px; color:#4a88c0;
    display:flex; justify-content:space-between;
">
    <span style="color:#fff; font-weight:bold;">ZHANG, ZHIMING</span>
    <span>ID: 350063 &nbsp;|&nbsp; DOB: 14/03/1955 M &nbsp;|&nbsp; 47 bpm</span>
    <span>CHEART2 &nbsp;|&nbsp; 20/04/2026 15:10 &nbsp;|&nbsp; NAEOTOM Alpha.Pro</span>
    <span>Medscan Merrylands &nbsp;|&nbsp; W:400 / C:40</span>
</div>

<!-- 5-panel grid (3 top + 2 bottom centred) -->
<div id="grid">
{panels_html}
</div>

{detail_html}

<!-- Watermark -->
<div style="
    position:fixed; bottom:6px; right:10px; z-index:99999;
    background:rgba(180,0,0,0.85); color:#fff;
    font-family:'Courier New',monospace; font-size:9px; font-weight:bold;
    letter-spacing:1px; padding:3px 8px; border-radius:3px;
    pointer-events:none;
">SIMULATION ONLY -- NOT FOR DIAGNOSTIC USE</div>
<div style="
    position:fixed; top:50%; left:50%;
    transform:translate(-50%,-50%) rotate(-30deg);
    color:rgba(180,0,0,0.07); font-size:40px; font-weight:bold;
    letter-spacing:4px; pointer-events:none; white-space:nowrap; z-index:99998;
">SIMULATION ONLY</div>

<script>
const SLICES = {slice_data_js};

// Seeded RNG for stable noise
function seededRng(seed) {{
    let s = seed;
    return function() {{ s=(s*9301+49297)%233280; return s/233280; }};
}}

function drawSlice(canvas, idx) {{
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const sl = SLICES[idx];
    const rng = seededRng(idx*7919+1);

    ctx.fillStyle='#000'; ctx.fillRect(0,0,W,H);

    // Chest wall
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(W/2,-20,W*0.52,H*0.65,0,0,Math.PI);
    ctx.strokeStyle='#c8c8c8'; ctx.lineWidth=14; ctx.stroke();
    ctx.restore();

    // Sternum
    ctx.save();
    ctx.beginPath();
    ctx.roundRect(W/2-18,10,36,20,4);
    ctx.fillStyle='#ddd'; ctx.fill();
    ctx.restore();

    // Heart mass
    const hx=W/2-14, hy=H/2-18;
    const grad=ctx.createRadialGradient(hx,hy,10,hx,hy,100);
    grad.addColorStop(0,'rgba(115,128,138,0.95)');
    grad.addColorStop(0.5,'rgba(85,98,108,0.88)');
    grad.addColorStop(1,'rgba(35,48,58,0)');
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(hx,hy,100,95,-0.15,0,Math.PI*2);
    ctx.fillStyle=grad; ctx.fill();
    ctx.restore();

    // RV
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(hx-36,hy-6,52,46,0.2,0,Math.PI*2);
    ctx.fillStyle='rgba(68,78,88,0.85)'; ctx.fill();
    ctx.restore();

    // LV
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(hx+32,hy+12,44,46,-0.1,0,Math.PI*2);
    ctx.fillStyle='rgba(82,92,102,0.90)'; ctx.fill();
    ctx.strokeStyle='rgba(155,165,175,0.5)'; ctx.lineWidth=5; ctx.stroke();
    ctx.restore();

    // Aorta
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(hx+52,hy-52,18,18,0,0,Math.PI*2);
    ctx.fillStyle='rgba(195,205,218,0.80)'; ctx.fill();
    ctx.strokeStyle='#bbb'; ctx.lineWidth=2; ctx.stroke();
    ctx.restore();

    // Descending aorta
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(hx-82,hy+38,14,14,0,0,Math.PI*2);
    ctx.fillStyle='rgba(185,195,212,0.80)'; ctx.fill();
    ctx.restore();

    // Spine
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(W/2+30,H-30,20,18,0,0,Math.PI*2);
    ctx.fillStyle='#d5d5d5'; ctx.fill();
    ctx.restore();

    // Lungs
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(W/2-120,H/2+8,56,80,0.2,0,Math.PI*2);
    ctx.fillStyle='rgba(3,3,3,0.96)'; ctx.fill();
    ctx.restore();
    ctx.save();
    ctx.beginPath();
    ctx.ellipse(W/2+138,H/2+12,44,76,-0.15,0,Math.PI*2);
    ctx.fillStyle='rgba(3,3,3,0.96)'; ctx.fill();
    ctx.restore();

    // Severity overlays
    if (sl.severity==='critical') {{
        // Soft plaque
        const sg=ctx.createRadialGradient(hx-12,hy-32,0,hx-12,hy-32,16);
        sg.addColorStop(0,'rgba(95,115,75,0.88)');
        sg.addColorStop(1,'rgba(60,80,40,0)');
        ctx.save(); ctx.beginPath();
        ctx.ellipse(hx-12,hy-32,14,12,rng()*Math.PI,0,Math.PI*2);
        ctx.fillStyle=sg; ctx.fill(); ctx.restore();
        // Stenosis ring
        ctx.save(); ctx.beginPath();
        ctx.arc(hx-12,hy-32,16,0,Math.PI*2);
        ctx.strokeStyle='rgba(255,80,80,0.55)'; ctx.lineWidth=1.5;
        ctx.setLineDash([3,2]); ctx.stroke(); ctx.setLineDash([]); ctx.restore();
    }} else if (sl.severity==='moderate') {{
        const pg=ctx.createRadialGradient(hx+40,hy-58,0,hx+40,hy-58,7);
        pg.addColorStop(0,'rgba(250,250,230,0.9)');
        pg.addColorStop(1,'rgba(200,200,180,0)');
        ctx.save(); ctx.beginPath();
        ctx.ellipse(hx+40,hy-58,6,5,rng()*Math.PI,0,Math.PI*2);
        ctx.fillStyle=pg; ctx.fill(); ctx.restore();
    }} else {{
        const pg=ctx.createRadialGradient(hx+20,hy+26,0,hx+20,hy+26,5);
        pg.addColorStop(0,'rgba(240,240,220,0.75)');
        pg.addColorStop(1,'rgba(200,200,180,0)');
        ctx.save(); ctx.beginPath();
        ctx.ellipse(hx+20,hy+26,4,3,rng()*Math.PI,0,Math.PI*2);
        ctx.fillStyle=pg; ctx.fill(); ctx.restore();
    }}

    // CT noise
    const img=ctx.getImageData(0,0,W,H), d=img.data;
    const nr=seededRng(idx*3141+59);
    for(let i=0;i<d.length;i+=4){{
        const n=(nr()-0.5)*16;
        d[i]=Math.min(255,Math.max(0,d[i]+n));
        d[i+1]=Math.min(255,Math.max(0,d[i+1]+n));
        d[i+2]=Math.min(255,Math.max(0,d[i+2]+n));
    }}
    ctx.putImageData(img,0,0);

    // Scanlines
    for(let y=0;y<H;y+=3){{ctx.fillStyle='rgba(0,0,0,0.05)';ctx.fillRect(0,y,W,1);}}
}}

// Draw all 5 canvases
for(let i=0;i<5;i++) {{
    const c=document.getElementById('c'+i);
    if(c) drawSlice(c,i);
}}

// Selection
const nexusPanel = {{
    selected: -1,
    selectSlice(idx) {{
        // Remove old highlight
        if(this.selected>=0) {{
            document.getElementById('panel-'+this.selected)?.classList.remove('panel-selected');
        }}
        this.selected=idx;
        document.getElementById('panel-'+idx)?.classList.add('panel-selected');
        const sl=SLICES[idx];
        const sevColors={{"critical":"#ff4444","moderate":"#f5c842","mild":"#44dd44"}};
        document.getElementById('detail-text').innerHTML=
            '<span style="color:'+sevColors[sl.severity]+'">'+sl.sl+' &mdash; '+sl.region+'</span>'
            +' &nbsp;|&nbsp; '+sl.finding
            +' &nbsp;|&nbsp; UID: '+sl.uid
            +' &nbsp;|&nbsp; SP: '+sl.sp;
    }}
}};

// Default: highlight SL3 (critical)
nexusPanel.selectSlice(2);
</script>
</body>
</html>"""
    return html
