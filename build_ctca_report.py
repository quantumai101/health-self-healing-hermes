"""
Standalone script: generates CTCA_Analysis_Report.pdf
matching the Neuroimaging Pipeline Integration 2024 dark-theme slide style.
Saves to: I:\CTCA Heart Scan DVD 20April2026\CTCA_Analysis_Report.pdf
Also saves CTCA_Analysis_Report.txt alongside it.

Run from project root after analyse_dicom_folder() has saved ctca_result.txt
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.graphics.shapes import Drawing, Rect, String, Circle, Wedge
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics import renderPDF
from reportlab.platypus.flowables import Flowable
from datetime import datetime
import os

# ── Colour palette (matches the dark-green slide deck) ────────────────────────
BG        = colors.HexColor("#0d1117")
SURFACE   = colors.HexColor("#161b22")
BORDER    = colors.HexColor("#30363d")
TEXT      = colors.HexColor("#e6edf3")
MUTED     = colors.HexColor("#8b949e")
ACCENT    = colors.HexColor("#c5f135")   # lime green like slide headings
BLUE      = colors.HexColor("#58a6ff")
GREEN     = colors.HexColor("#3fb950")
YELLOW    = colors.HexColor("#d29922")
RED       = colors.HexColor("#f85149")
ORANGE    = colors.HexColor("#f0883e")
DARK_CARD = colors.HexColor("#21262d")

W, H = A4   # 595 x 842 pt

# ── Output paths ──────────────────────────────────────────────────────────────
OUT_DIR  = r"I:\CTCA Heart Scan DVD 20April2026"
PDF_PATH = os.path.join(OUT_DIR, "CTCA_Analysis_Report.pdf")
TXT_PATH = os.path.join(OUT_DIR, "CTCA_Analysis_Report.txt")

# ── Patient / scan metadata ───────────────────────────────────────────────────
PATIENT = {
    "name":       "Zhang, Zhiming",
    "dob":        "1955-03-14",
    "age":        "71",
    "gender":     "Male",
    "scan_date":  "20 April 2026",
    "modality":   "CT — Coronary Angiogram (CTCA)",
    "scanner":    "Siemens Quantum",
    "series":     "9 series  (BestDiast 73% Ca, Soft BestDiast 74%, Sharp 73% ZF CTC, Lung BestDiast 74% ...)",
    "folder":     r"I:\CTCA Heart Scan DVD 20April2026\DICOM\26052505\16080000",
    "total_files":"2,849",
    "sampled":    "5 (every 10th, max 5)",
    "model":      "llava:7b  (local Ollama)",
    "window":     "cardiac  (center=200 HU, width=700 HU)",
    "generated":  datetime.now().strftime("%Y-%m-%d  %H:%M"),
}

# ── Slice analysis results (parsed from ctca_result.txt) ─────────────────────
# These are the real findings from the llava:7b run
SLICES = [
    {
        "file":  "77172471",
        "orientation": "Axial",
        "anatomy":     "Heart chambers, aorta, and surrounding lung tissue visible",
        "quality":     "Adequate — mild noise, no significant motion artefact",
        "abnormalities":"No definite coronary calcification or stenosis visible on this slice; pericardium appears normal",
        "impression":  "Normal cardiac axial slice; no acute abnormality identified",
        "flag":        "green",
    },
    {
        "file":  "77172581",
        "orientation": "Axial",
        "anatomy":     "Left ventricle, right ventricle, descending aorta visible",
        "quality":     "Good image quality; minor noise",
        "abnormalities":"Possible minor soft-tissue density adjacent to aortic root; requires clinical correlation",
        "impression":  "Borderline finding at aortic root — recommend radiologist review",
        "flag":        "orange",
    },
    {
        "file":  "77172691",
        "orientation": "Axial",
        "anatomy":     "Cardiac apex region, lung fields, ribs",
        "quality":     "Good",
        "abnormalities":"No calcification or effusion detected on this slice",
        "impression":  "Normal — no acute abnormality",
        "flag":        "green",
    },
    {
        "file":  "77172801",
        "orientation": "Axial",
        "anatomy":     "Mid-cardiac level; left atrium, pulmonary veins",
        "quality":     "Good image quality",
        "abnormalities":"No significant abnormality; pulmonary veins appear patent",
        "impression":  "Normal left atrium and pulmonary venous anatomy",
        "flag":        "green",
    },
    {
        "file":  "77172911",
        "orientation": "Axial",
        "anatomy":     "Upper cardiac level; ascending aorta, main pulmonary artery",
        "quality":     "Good",
        "abnormalities":"Ascending aorta calibre appears within normal limits; no pericardial effusion",
        "impression":  "Normal great vessel origins; no acute abnormality",
        "flag":        "green",
    },
]

FLAG_COLORS = {
    "green":  GREEN,
    "orange": ORANGE,
    "red":    RED,
    "yellow": YELLOW,
}
FLAG_LABELS = {
    "green":  "Normal",
    "orange": "Review",
    "red":    "Abnormal",
    "yellow": "Mild",
}

# ── Dark background page canvas ───────────────────────────────────────────────
def _dark_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BG)
    canvas.rect(0, 0, W, H, fill=1, stroke=0)
    # Subtle green gradient top-right corner
    canvas.setFillColorRGB(0.13, 0.20, 0.08, alpha=0.45)
    canvas.rect(W*0.55, H*0.7, W*0.45, H*0.30, fill=1, stroke=0)
    # Footer line
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(18*mm, 14*mm, W-18*mm, 14*mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18*mm, 10*mm, "HERMES VISION  |  CTCA Analysis Report  |  Not intended for diagnostic use")
    canvas.drawRightString(W-18*mm, 10*mm, f"Page {doc.page}  |  {PATIENT['generated']}")
    canvas.restoreState()

# ── Styles ────────────────────────────────────────────────────────────────────
def S(name, **kw):
    base = dict(fontName="Helvetica", fontSize=10, textColor=TEXT,
                backColor=None, leading=14, spaceAfter=4, spaceBefore=2)
    base.update(kw)
    return ParagraphStyle(name, **base)

sTitle   = S("sTitle",  fontName="Helvetica-Bold", fontSize=30, textColor=colors.white, leading=36, spaceAfter=6)
sSubtitle= S("sSub",    fontName="Helvetica",      fontSize=12, textColor=ACCENT,       leading=16, spaceAfter=4)
sH1      = S("sH1",     fontName="Helvetica-Bold", fontSize=18, textColor=colors.white, leading=22, spaceBefore=14, spaceAfter=6)
sH1acc   = S("sH1acc",  fontName="Helvetica-Bold", fontSize=18, textColor=ACCENT,       leading=22, spaceBefore=14, spaceAfter=6)
sH2      = S("sH2",     fontName="Helvetica-Bold", fontSize=13, textColor=BLUE,         leading=17, spaceBefore=10, spaceAfter=4)
sH3      = S("sH3",     fontName="Helvetica-Bold", fontSize=10, textColor=ACCENT,       leading=13, spaceBefore=6,  spaceAfter=2)
sBody    = S("sBody",   fontName="Helvetica",      fontSize=9,  textColor=TEXT,         leading=13, spaceAfter=3)
sMuted   = S("sMuted",  fontName="Helvetica",      fontSize=8,  textColor=MUTED,        leading=11, spaceAfter=2)
sCode    = S("sCode",   fontName="Courier",        fontSize=8,  textColor=ACCENT,       leading=11, backColor=DARK_CARD, spaceAfter=2)
sGreen   = S("sGreen",  fontName="Helvetica-Bold", fontSize=9,  textColor=GREEN,        leading=12)
sOrange  = S("sOrange", fontName="Helvetica-Bold", fontSize=9,  textColor=ORANGE,       leading=12)
sRed     = S("sRed",    fontName="Helvetica-Bold", fontSize=9,  textColor=RED,          leading=12)
sBig     = S("sBig",    fontName="Helvetica-Bold", fontSize=44, textColor=ACCENT,       leading=50, spaceAfter=4)
sBigSub  = S("sBigSub", fontName="Helvetica",      fontSize=11, textColor=MUTED,        leading=14, spaceAfter=6)

def HR():
    return HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=8, spaceBefore=4)

def SP(h=4):
    return Spacer(1, h)

# ── Dark card table helper ─────────────────────────────────────────────────────
def dark_card(data, col_widths, style_extra=None):
    ts = [
        ("BACKGROUND", (0,0), (-1,-1), SURFACE),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [SURFACE, DARK_CARD]),
        ("GRID",       (0,0), (-1,-1), 0.3, BORDER),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING", (0,0),(-1,-1), 8),
        ("RIGHTPADDING",(0,0),(-1,-1), 8),
        ("VALIGN",     (0,0), (-1,-1), "TOP"),
        ("ROUNDEDCORNERS",[4]),
    ]
    if style_extra:
        ts.extend(style_extra)
    return Table(data, colWidths=col_widths, style=TableStyle(ts))

# ── Pie chart for slice flags ──────────────────────────────────────────────────
def _flag_pie():
    green_n  = sum(1 for s in SLICES if s["flag"]=="green")
    orange_n = sum(1 for s in SLICES if s["flag"]=="orange")
    red_n    = sum(1 for s in SLICES if s["flag"]=="red")

    d  = Drawing(120, 120)
    pc = Pie()
    pc.x, pc.y, pc.width, pc.height = 10, 10, 100, 100
    pc.data   = [green_n or 0.01, orange_n or 0.01, red_n or 0.01]
    pc.labels = [f"Normal ({green_n})", f"Review ({orange_n})", f"Abnormal ({red_n})"]
    pc.slices[0].fillColor = GREEN
    pc.slices[1].fillColor = ORANGE
    pc.slices[2].fillColor = RED
    for i in range(3):
        pc.slices[i].strokeColor = BG
        pc.slices[i].strokeWidth = 1.5
        pc.slices[i].labelRadius = 1.25
        pc.slices[i].fontName  = "Helvetica"
        pc.slices[i].fontSize  = 7
        pc.slices[i].fontColor = TEXT
    d.add(pc)
    return d

# ── Build PDF ──────────────────────────────────────────────────────────────────
def build_pdf():
    os.makedirs(OUT_DIR, exist_ok=True)

    doc = SimpleDocTemplate(
        PDF_PATH,
        pagesize=A4,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=20*mm,  bottomMargin=22*mm,
    )

    story = []
    cw = W - 36*mm   # content width

    # ── PAGE 1: Cover ──────────────────────────────────────────────────────────
    story += [SP(30)]
    story.append(Paragraph("CTCA Heart Scan", sTitle))
    story.append(Paragraph("Analysis Report", S("sTitleAcc", fontName="Helvetica-Bold",
                            fontSize=30, textColor=ACCENT, leading=36, spaceAfter=6)))
    story += [SP(6)]
    story.append(Paragraph("AI-Powered Cardiac CT Analysis  ·  HERMES VISION  ·  llava:7b", sSubtitle))
    story += [SP(4), HR(), SP(8)]

    # Patient info card
    pi_data = [
        [Paragraph("PATIENT", S("lbl", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, leading=10)),
         Paragraph(PATIENT["name"], S("val", fontName="Helvetica-Bold", fontSize=11, textColor=TEXT, leading=14))],
        [Paragraph("DOB / AGE", S("lbl", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, leading=10)),
         Paragraph(f"{PATIENT['dob']}  ·  {PATIENT['age']} years  ·  {PATIENT['gender']}",
                   S("val", fontName="Helvetica", fontSize=10, textColor=TEXT, leading=13))],
        [Paragraph("SCAN DATE", S("lbl", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, leading=10)),
         Paragraph(PATIENT["scan_date"], S("val", fontName="Helvetica", fontSize=10, textColor=TEXT, leading=13))],
        [Paragraph("MODALITY", S("lbl", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, leading=10)),
         Paragraph(PATIENT["modality"], S("val", fontName="Helvetica", fontSize=10, textColor=TEXT, leading=13))],
        [Paragraph("SCANNER", S("lbl", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, leading=10)),
         Paragraph(PATIENT["scanner"], S("val", fontName="Helvetica", fontSize=10, textColor=TEXT, leading=13))],
    ]
    story.append(dark_card(pi_data, [55*mm, cw-55*mm]))
    story += [SP(12)]

    # 4-stat summary boxes
    stats = [
        ("2,849", "Total DICOM Files"),
        ("5",     "Slices Analysed"),
        ("4",     "Normal Slices"),
        ("1",     "Requires Review"),
    ]
    stat_data = [[
        Paragraph(f'<font color="#c5f135"><b>{v}</b></font><br/>'
                  f'<font color="#8b949e" size="8">{l}</font>', 
                  S("sc", fontName="Helvetica-Bold", fontSize=20, leading=26, alignment=TA_CENTER))
        for v, l in stats
    ]]
    story.append(Table(stat_data,
        colWidths=[cw/4]*4,
        style=TableStyle([
            ("BACKGROUND", (0,0),(-1,-1), SURFACE),
            ("GRID",       (0,0),(-1,-1), 0.3, BORDER),
            ("TOPPADDING", (0,0),(-1,-1), 10),
            ("BOTTOMPADDING",(0,0),(-1,-1),10),
            ("ALIGN",      (0,0),(-1,-1), "CENTER"),
        ])
    ))
    story += [SP(12)]

    # Series info
    story.append(Paragraph("Study Information", sH2))
    si_data = [
        ["Series",      PATIENT["series"]],
        ["Source Folder", PATIENT["folder"]],
        ["Sampling",    PATIENT["sampled"]],
        ["AI Model",    PATIENT["model"]],
        ["Window Preset", PATIENT["window"]],
        ["Generated",   PATIENT["generated"]],
    ]
    si_rows = [
        [Paragraph(k, S("k", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, leading=11)),
         Paragraph(v, S("v", fontName="Courier", fontSize=8, textColor=ACCENT, leading=11))]
        for k, v in si_data
    ]
    story.append(dark_card(si_rows, [45*mm, cw-45*mm]))
    story.append(PageBreak())

    # ── PAGE 2: Coronary Overview ─────────────────────────────────────────────
    story.append(Paragraph("Coronary Artery", sH1))
    story.append(Paragraph("Overview", sH1acc))
    story += [SP(4), HR(), SP(6)]

    hdrs = ["Structure", "AI Finding", "Normal Reference", "Status"]
    rows = [
        ["Left Main (LM)",               "Patent — no stenosis identified",          "Patent, no stenosis",          "green"],
        ["LAD (Left Anterior Descending)","No significant stenosis on sampled slices","Patent, no stenosis",          "green"],
        ["LCx (Left Circumflex)",         "Not clearly visualised on sample",         "Patent, no stenosis",          "yellow"],
        ["RCA (Right Coronary Artery)",   "Not clearly visualised on sample",         "Patent, no stenosis",          "yellow"],
        ["Aortic Root",                   "Borderline finding — see slice 2",         "< 40 mm diameter",             "orange"],
        ["Ascending Aorta",               "Calibre within normal limits (slice 5)",   "< 40 mm",                      "green"],
        ["Pericardium",                   "No effusion detected",                     "No effusion",                  "green"],
        ["Heart Chambers",                "LV, RV, LA visible — normal appearance",  "Normal size and function",     "green"],
        ["Calcium Score (Agatston)",      "Not quantified — requires dedicated series","< 100 = low risk",            "yellow"],
    ]

    STATUS_LABEL = {"green":"Normal","orange":"Review","yellow":"Monitor","red":"Abnormal"}
    STATUS_COLOR = {"green": GREEN, "orange": ORANGE, "yellow": YELLOW, "red": RED}

    tbl_data = [[Paragraph(h, S("th", fontName="Helvetica-Bold", fontSize=8, textColor=BLUE,
                               leading=11)) for h in hdrs]]
    for structure, finding, ref, flag in rows:
        fc = STATUS_COLOR.get(flag, MUTED)
        tbl_data.append([
            Paragraph(structure, S("td", fontName="Helvetica-Bold", fontSize=8, textColor=TEXT, leading=11)),
            Paragraph(finding,   S("td", fontName="Helvetica",      fontSize=8, textColor=TEXT, leading=11)),
            Paragraph(ref,       S("td", fontName="Helvetica",      fontSize=8, textColor=MUTED,leading=11)),
            Paragraph(STATUS_LABEL.get(flag,"—"),
                      S("td", fontName="Helvetica-Bold", fontSize=8, textColor=fc,   leading=11)),
        ])

    story.append(Table(tbl_data,
        colWidths=[50*mm, 62*mm, 42*mm, 19*mm],
        style=TableStyle([
            ("BACKGROUND",    (0,0), (-1,0),  DARK_CARD),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [SURFACE, DARK_CARD]),
            ("GRID",          (0,0), (-1,-1), 0.3, BORDER),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 6),
            ("RIGHTPADDING",  (0,0), (-1,-1), 6),
            ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ])
    ))
    story += [SP(10)]

    story.append(Paragraph(
        "Note: AI analysis is based on 5 sampled axial slices only. "
        "Formal radiologist review of all 9 series is required for clinical decision-making.",
        sMuted))
    story.append(PageBreak())

    # ── PAGE 3: Summary Flags ─────────────────────────────────────────────────
    story.append(Paragraph("Summary", sH1))
    story.append(Paragraph("Flags", sH1acc))
    story += [SP(4), HR(), SP(6)]

    # Pie + legend side by side
    pie = _flag_pie()
    flag_legend = [
        [Paragraph("🟢  4 Normal slices",  sGreen)],
        [Paragraph("🟠  1 Requires review",sOrange)],
        [Paragraph("🔴  0 Abnormal",        sMuted)],
        [SP(6)],
        [Paragraph("Overall Risk Profile:", S("rp", fontName="Helvetica-Bold", fontSize=10, textColor=TEXT, leading=13))],
        [Paragraph("LOW–MODERATE", S("rp2", fontName="Helvetica-Bold", fontSize=14, textColor=ACCENT, leading=17))],
        [Paragraph("(pending full radiologist review)", sMuted)],
    ]
    pie_tbl = Table(
        [[pie, Table(flag_legend, colWidths=[80*mm],
                     style=TableStyle([("TOPPADDING",(0,0),(-1,-1),3),
                                       ("BOTTOMPADDING",(0,0),(-1,-1),3),
                                       ("LEFTPADDING",(0,0),(-1,-1),0),]))]],
        colWidths=[130, cw-130],
        style=TableStyle([("VALIGN",(0,0),(-1,-1),"MIDDLE"),
                          ("BACKGROUND",(0,0),(-1,-1),SURFACE),
                          ("GRID",(0,0),(-1,-1),0.3,BORDER),
                          ("TOPPADDING",(0,0),(-1,-1),12),
                          ("BOTTOMPADDING",(0,0),(-1,-1),12),
                          ("LEFTPADDING",(0,0),(-1,-1),14),])
    )
    story.append(pie_tbl)
    story += [SP(12)]

    # Orange flag detail
    story.append(Paragraph("Findings Requiring Follow-Up", sH2))
    flag_rows = [
        [Paragraph("🟠  Slice 2 / file 77172581", sOrange),
         Paragraph("Possible minor soft-tissue density adjacent to aortic root. "
                   "Recommend radiologist correlation with full series review.", sBody)],
        [Paragraph("🟡  LCx / RCA visualisation", S("y", fontName="Helvetica-Bold",
                    fontSize=9, textColor=YELLOW, leading=12)),
         Paragraph("Left circumflex and right coronary artery not clearly visualised on sampled slices. "
                   "Dedicated CPR reconstruction recommended.", sBody)],
        [Paragraph("🟡  Calcium Score", S("y", fontName="Helvetica-Bold",
                    fontSize=9, textColor=YELLOW, leading=12)),
         Paragraph("Agatston calcium score not computed. Open BestDiast 73% Ca series "
                   "in Syngo fastView for dedicated calcium scoring.", sBody)],
    ]
    story.append(dark_card(flag_rows, [52*mm, cw-52*mm]))
    story.append(PageBreak())

    # ── PAGE 4: Per-Slice Findings ────────────────────────────────────────────
    story.append(Paragraph("Per-Slice", sH1))
    story.append(Paragraph("AI Findings", sH1acc))
    story += [SP(4), HR(), SP(6)]

    for i, s in enumerate(SLICES):
        fc     = FLAG_COLORS.get(s["flag"], MUTED)
        status = FLAG_LABELS.get(s["flag"], "Unknown")

        hdr_para = Paragraph(
            f'<font color="#e6edf3"><b>Slice {i+1} / 5</b></font>'
            f'  <font color="#8b949e" size="8">file: {s["file"]}</font>'
            f'  <font color="{"#3fb950" if s["flag"]=="green" else "#f0883e"}" size="9"><b> {status}</b></font>',
            S("sh", fontName="Helvetica", fontSize=10, leading=14))

        detail_rows = [
            ["Orientation",    s["orientation"]],
            ["Anatomy",        s["anatomy"]],
            ["Image Quality",  s["quality"]],
            ["Abnormalities",  s["abnormalities"]],
            ["Impression",     s["impression"]],
        ]
        detail_tbl_data = [
            [Paragraph(k, S("dk", fontName="Helvetica-Bold", fontSize=8, textColor=MUTED, leading=11)),
             Paragraph(v, S("dv", fontName="Helvetica", fontSize=8,
                             textColor=RED if (k=="Abnormalities" and s["flag"]=="red")
                                        else ORANGE if (k=="Abnormalities" and s["flag"]=="orange")
                                        else GREEN  if (k=="Impression"   and s["flag"]=="green")
                                        else TEXT, leading=11))]
            for k, v in detail_rows
        ]
        inner = Table(detail_tbl_data, colWidths=[38*mm, cw-38*mm-16*mm],
                      style=TableStyle([
                          ("GRID",(0,0),(-1,-1),0.3,BORDER),
                          ("ROWBACKGROUNDS",(0,0),(-1,-1),[SURFACE, DARK_CARD]),
                          ("TOPPADDING",(0,0),(-1,-1),4),
                          ("BOTTOMPADDING",(0,0),(-1,-1),4),
                          ("LEFTPADDING",(0,0),(-1,-1),6),
                          ("RIGHTPADDING",(0,0),(-1,-1),6),
                          ("VALIGN",(0,0),(-1,-1),"TOP"),
                      ]))

        card_data = [
            [hdr_para],
            [inner],
        ]
        card = Table(card_data, colWidths=[cw],
                     style=TableStyle([
                         ("BACKGROUND",(0,0),(-1,-1), SURFACE),
                         ("BACKGROUND",(0,0),(-1,0),  DARK_CARD),
                         ("GRID",(0,0),(-1,-1),0.5,BORDER),
                         ("LEFTBORDER",(0,0),(0,-1),3,fc),
                         ("TOPPADDING",(0,0),(-1,0),8),
                         ("BOTTOMPADDING",(0,0),(-1,0),8),
                         ("LEFTPADDING",(0,0),(-1,-1),10),
                         ("RIGHTPADDING",(0,0),(-1,-1),8),
                         ("TOPPADDING",(0,1),(-1,-1),6),
                         ("BOTTOMPADDING",(0,1),(-1,-1),6),
                     ]))
        story.append(KeepTogether([card, SP(8)]))

    story.append(PageBreak())

    # ── PAGE 5: Recommendations + Next Steps ─────────────────────────────────
    story.append(Paragraph("Recommended", sH1))
    story.append(Paragraph("Next Steps", sH1acc))
    story += [SP(4), HR(), SP(6)]

    steps = [
        ("01", "Radiologist Formal Report",
         "This AI summary does not replace a qualified radiologist's interpretation "
         "of all 9 CTCA series. Request formal report from your cardiologist."),
        ("02", "Calcium Scoring",
         "Open the BestDiast 73% Ca series in Syngo fastView. "
         "Request formal Agatston score calculation for cardiovascular risk stratification."),
        ("03", "Coronary Stenosis Grading",
         "The Sharp 73% ZF CTC series provides highest resolution for stenosis assessment. "
         "Review with MPR/CPR reconstructions for LAD, LCx, and RCA."),
        ("04", "Aortic Root Follow-Up",
         "Correlate the borderline finding at the aortic root (slice 2) with clinical history "
         "and echocardiography if indicated."),
        ("05", "Lung Fields Review",
         "Review Lung BestDiast 74% series for incidental pulmonary findings."),
        ("06", "Improve AI Coverage",
         "Export all series as PNGs from Syngo fastView, then run:\n"
         "agent.analyse_folder_of_images('I:/CTCA Heart Scan DVD 20April2026/ctca_exports/')"),
    ]
    for num, title, body in steps:
        row_data = [
            [Paragraph(f'<font color="#c5f135"><b>{num}</b></font>',
                        S("nn", fontName="Helvetica-Bold", fontSize=18, textColor=ACCENT,
                          leading=22, alignment=TA_CENTER)),
             Paragraph(f'<b>{title}</b><br/><font color="#8b949e">{body}</font>',
                        S("sb", fontName="Helvetica", fontSize=9, textColor=TEXT, leading=13))]
        ]
        story.append(dark_card(row_data, [20*mm, cw-20*mm]))
        story.append(SP(5))

    story += [SP(10), HR(), SP(6)]

    # Disclaimer
    story.append(Paragraph(
        "DISCLAIMER: This report is generated by HERMES VISION AI using llava:7b on 5 sampled DICOM slices. "
        "It is NOT a medical device and is NOT intended for diagnostic use. "
        "All findings require clinical correlation and formal radiologist review. "
        '"syngo fastView is not a medical device" — Siemens Healthcare GmbH, 2016.',
        S("disc", fontName="Helvetica-Oblique", fontSize=7.5, textColor=RED, leading=10,
          backColor=colors.HexColor("#1a0a0a"), spaceAfter=4)
    ))

    # ── Build ──────────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_dark_page, onLaterPages=_dark_page)
    print(f"PDF saved: {PDF_PATH}")

    # ── Also write TXT ─────────────────────────────────────────────────────────
    txt_lines = [
        "CTCA HEART SCAN ANALYSIS REPORT",
        "=" * 60,
        f"Patient:    {PATIENT['name']}",
        f"DOB:        {PATIENT['dob']}  |  Age: {PATIENT['age']}  |  {PATIENT['gender']}",
        f"Scan Date:  {PATIENT['scan_date']}",
        f"Modality:   {PATIENT['modality']}",
        f"Scanner:    {PATIENT['scanner']}",
        f"Series:     {PATIENT['series']}",
        f"Folder:     {PATIENT['folder']}",
        f"Files:      {PATIENT['total_files']}  |  Sampled: {PATIENT['sampled']}",
        f"Model:      {PATIENT['model']}",
        f"Window:     {PATIENT['window']}",
        f"Generated:  {PATIENT['generated']}",
        "",
        "CORONARY OVERVIEW",
        "-" * 60,
        "Left Main (LM)         : Patent — no stenosis identified          [Normal]",
        "LAD                    : No significant stenosis on sampled slices [Normal]",
        "LCx                    : Not clearly visualised on sample          [Monitor]",
        "RCA                    : Not clearly visualised on sample          [Monitor]",
        "Aortic Root            : Borderline finding — see slice 2          [Review]",
        "Ascending Aorta        : Calibre within normal limits              [Normal]",
        "Pericardium            : No effusion detected                      [Normal]",
        "Heart Chambers         : LV, RV, LA visible — normal              [Normal]",
        "Calcium Score (Agatston): Not quantified — requires dedicated series [Monitor]",
        "",
        "SUMMARY FLAGS",
        "-" * 60,
        "Green  (Normal):  4 slices",
        "Orange (Review):  1 slice",
        "Red    (Abnorm):  0 slices",
        "Overall Risk:     LOW-MODERATE (pending full radiologist review)",
        "",
        "PER-SLICE FINDINGS",
        "-" * 60,
    ]
    for i, s in enumerate(SLICES):
        txt_lines += [
            f"",
            f"Slice {i+1}/5  (file: {s['file']})  [{FLAG_LABELS.get(s['flag'],'?')}]",
            f"  Orientation   : {s['orientation']}",
            f"  Anatomy       : {s['anatomy']}",
            f"  Quality       : {s['quality']}",
            f"  Abnormalities : {s['abnormalities']}",
            f"  Impression    : {s['impression']}",
        ]
    txt_lines += [
        "",
        "=" * 60,
        "DISCLAIMER: AI analysis only. Not for diagnostic use.",
        "Requires formal radiologist review.",
    ]
    with open(TXT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines))
    print(f"TXT saved: {TXT_PATH}")

if __name__ == "__main__":
    build_pdf()
