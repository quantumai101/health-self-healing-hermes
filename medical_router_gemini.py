import os, sys, json, time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
for _ep in [Path(__file__).parent/".env",
            Path.home()/"Desktop"/"health-self-healing-hermes"/".env"]:
    if _ep.exists():
        load_dotenv(dotenv_path=_ep, override=True)
        break
else:
    load_dotenv(override=True)
try:
    from tqdm import tqdm
    from colorama import Fore, Style, init
    init(autoreset=True)
except ImportError:
    class Fore:
        RED=GREEN=YELLOW=CYAN=WHITE=""
    class Style:
        RESET_ALL=BRIGHT=""
    def tqdm(x,**k): return x
from google import genai
from google.genai import types
import pydicom, numpy as np, io
from PIL import Image
API_KEY    = os.getenv("GOOGLE_API_KEY","") or os.getenv("GEMINI_API_KEY","")
MRI_ROOT   = os.getenv("MRI_LOCAL_PATH", r"C:\MRI Brain 5Jan2024").strip(chr(34)).strip("'")
REPORTS_IN = os.getenv("MEDICAL_REPORTS_PATH", r"C:\Medical Reports 17Feb2026").strip(chr(34)).strip("'")
OUTPUT_TXT = str(Path(REPORTS_IN)/"MRI_Analysis_Report.txt")
OUTPUT_HTML= str(Path(REPORTS_IN)/"MRI_Analysis_Report.html")
MODEL      = "gemini-2.5-flash"
DICOM_BASE = Path(MRI_ROOT)/"DICOM"/"PA000001"/"ST000001"
PATIENT    = dict(name="Zhang Zhi Ming",dob="14/03/1955",age=69,sex="Male",
                  scan_date="05 January 2024",facility="Castlereagh Imaging",
                  known_history="Benign Prostatic Hypertrophy (BPH/Hyperplasia). Recent CTCA does not confirm hypertension or cardiac disease.")
SERIES_ROUTES = {
    "T2_FLAIR":dict(priority=3,agent="AXIOM",role="wmh"),
    "FLAIR":   dict(priority=3,agent="AXIOM",role="wmh"),
    "T1_TIRM": dict(priority=2,agent="AXIOM",role="t1volume"),
    "TIRM":    dict(priority=2,agent="AXIOM",role="t1volume"),
    "T2_TSE":  dict(priority=1,agent="AXIOM",role="t2struct"),
    "TOF_3D":  dict(priority=1,agent="AXIOM",role="vessels"),
    "REPORT":  dict(priority=3,agent="NOVA", role="pdf_report"),
}
def setup():
    if not API_KEY:
        print("ERROR: GOOGLE_API_KEY not found in .env"); sys.exit(1)
    print(f"Key: {API_KEY[:8]}...")
    return genai.Client(api_key=API_KEY)
def discover_series():
    series_list=[]
    for se_dir in sorted(DICOM_BASE.iterdir()):
        if not se_dir.is_dir(): continue
        images=[f for f in sorted(se_dir.iterdir()) if f.is_file() and f.suffix.lower() not in {".zip",".gz",".tar",".rar",".txt",".xml",".json"}]
        if not images: continue
        mid=images[len(images)//2]
        try:
            ds=pydicom.dcmread(str(mid),stop_before_pixels=True)
            desc=getattr(ds,"SeriesDescription","").strip()
        except: continue
        if not desc: continue
        route=None
        for kw,cfg in SERIES_ROUTES.items():
            if kw.upper() in desc.upper(): route=cfg; break
        if not route: continue
        series_list.append(dict(se_dir=se_dir,se_name=se_dir.name,desc=desc,images=images,n_images=len(images),**route))
    return sorted(series_list,key=lambda x:-x["priority"])
def dicom_to_png(path):
    try:
        ds=pydicom.dcmread(str(path)); arr=ds.pixel_array.astype(float)
        if arr.ndim==3: arr=arr[arr.shape[0]//2]
        lo,hi=arr.min(),arr.max()
        if hi==lo: return None
        arr=((arr-lo)/(hi-lo)*255).astype(np.uint8)
        img=Image.fromarray(arr).convert("RGB"); w,h=img.size
        if max(w,h)>1024: s=1024/max(w,h); img=img.resize((int(w*s),int(h*s)),Image.LANCZOS)
        buf=io.BytesIO(); img.save(buf,format="PNG"); return buf.getvalue()
    except Exception as e: print(f"  DICOM->PNG failed: {e}"); return None
def get_prompt(role):
    p=PATIENT
    hdr=f"Patient: {p[chr(110)+chr(97)+chr(109)+chr(101)]}, DOB {p[chr(100)+chr(111)+chr(98)]}, Age {p[chr(97)+chr(103)+chr(101)]}, {p[chr(115)+chr(101)+chr(120)]}. Scan: {p[chr(115)+chr(99)+chr(97)+chr(110)+chr(95)+chr(100)+chr(97)+chr(116)+chr(101)]}, {p[chr(102)+chr(97)+chr(99)+chr(105)+chr(108)+chr(105)+chr(116)+chr(121)]}. History: {p[chr(107)+chr(110)+chr(111)+chr(119)+chr(110)+chr(95)+chr(104)+chr(105)+chr(115)+chr(116)+chr(111)+chr(114)+chr(121)]}\n\n"
    if role=="wmh":
        return hdr+f"""Analyse T2-FLAIR slices. Return JSON only:
{{"sequence":"T2-FLAIR","wmh_periventricular_fazekas":0,"wmh_deep_fazekas":0,"wmh_burden":"NONE/MILD/MODERATE/SEVERE","wmh_pct_estimate":"~X%","lacunes":false,"lacune_count":"0","enlarged_perivascular_spaces_epvs":"NONE/MILD/MODERATE/SEVERE","epvs_location":"none/basal ganglia/white matter/both","epvs_glymphatic_implication":"normal/mildly impaired/moderately impaired","microvascular_significance":"...","age_comparison":"better/average/worse than expected for age {p[chr(97)+chr(103)+chr(101)]}","urgent_flag":false,"findings_summary":"..."}}"""
    elif role=="t1volume":
        return hdr+f"""Analyse T1/TIRM slices. Return JSON only:
{{"sequence":"T1_TIRM","grey_matter_pct":"~X%","white_matter_pct":"~X%","csf_pct":"~X%","gm_status":"NORMAL/MILDLY_REDUCED/MODERATELY_REDUCED","cortical_atrophy_grade":0,"mta_score_left":0.0,"mta_score_right":0.0,"mta_interpretation":"normal for age/borderline/abnormal","hippocampal_occupancy_hoc":"~X%","hoc_interpretation":"normal >60%/borderline/low risk","regional_atrophy":{{"frontal":"none/mild","temporal":"none/mild","hippocampal":"none/mild"}},"ventricular_size":"normal/enlarged","brain_age_estimate":"~X years","brain_age_vs_chronological":"younger/same/older than {p[chr(97)+chr(103)+chr(101)]}","findings_summary":"..."}}"""
    elif role=="vessels":
        return hdr+"""Analyse TOF MRA. Patient had basilar dolichoectasia in 2022. Return JSON only:
{"sequence":"TOF_MRA","circle_of_willis":"complete/incomplete","basilar_artery_diameter_mm":"Xmm","basilar_dolichoectasia":"none/mild/moderate/severe","basilar_vs_2022":"stable/increased/decreased","mca_bilateral":"normal/stenosis","aca_bilateral":"normal/stenosis","pca_bilateral":"normal/stenosis","stenosis_detected":false,"stenosis_details":"none","aneurysm":false,"overall_vasculature":"normal/abnormal","findings_summary":"..."}"""
    elif role=="pdf_report":
        return hdr+"""Analyse report text. Return JSON only:
{"report_type":"radiology","key_findings":[],"diagnoses":[],"recommendations":[],"urgent_flag":false,"findings_summary":"..."}"""
    else:
        return hdr+"""Analyse T2 slices. Return JSON only:
{"sequence":"T2_TSE","basal_ganglia":"normal","cerebellum":"normal","focal_lesions":false,"overall_structure":"normal","findings_summary":"..."}"""
def analyse(client,series):
    role=series["role"]; prompt=get_prompt(role)
    images=series["images"]; slices=images[len(images)//4:len(images)*3//4]
    picks=slices[::max(1,len(slices)//3)][:3]
    parts=[types.Part.from_text(text=prompt)]; png_count=0
    for sl in picks:
        png=dicom_to_png(sl)
        if png: parts.append(types.Part.from_bytes(data=png,mime_type="image/png")); png_count+=1
    if len(parts)==1: return {"error":"no slices","series":series["desc"],"slices_analysed":0}
    for attempt in range(3):
        try:
            resp=client.models.generate_content(model=MODEL,contents=parts)
            raw=resp.text.strip()
            if "```" in raw: raw="\n".join(l for l in raw.split("\n") if not l.strip().startswith("```"))
            result=json.loads(raw.strip()); result["slices_analysed"]=png_count; break
        except json.JSONDecodeError: result={"raw_analysis":resp.text,"parse_error":True,"slices_analysed":png_count}; break
        except Exception as e:
            if "429" in str(e): time.sleep(60)
            elif attempt==2: result={"error":str(e),"slices_analysed":0}
            else: time.sleep(5)
    result.update(series_name=series["se_name"],series_desc=series["desc"],total_images_in_series=series["n_images"],agent=series["agent"],role=role)
    return result
def sentinel_summary(client,results):
    try:
        findings=json.dumps(results,indent=2)[:25000]
        prompt=f"""You are SENTINEL. Compile MASTER BRAIN HEALTH REPORT.
Patient: {PATIENT["name"]} | Age: {PATIENT["age"]} | {PATIENT["scan_date"]}
History: {PATIENT["known_history"]}
Use markdown tables and traffic lights 🟢🟡🔴. Include:
1. OVERALL RATING (EXCELLENT/GOOD/FAIR/CONCERNING/CRITICAL)
2. GREY & WHITE MATTER table vs normal age {PATIENT["age"]}yo male
3. MTA SCORE & HIPPOCAMPUS table (mta_score_left, mta_score_right, HOC%)
4. MICROVASCULAR DISEASE table (Fazekas grades, WMH%, lacunes)
5. EPVS / GLYMPHATIC SYSTEM assessment
6. CEREBROVASCULAR table (basilar diameter, dolichoectasia vs 2022)
7. BRAIN AGE vs chronological {PATIENT["age"]}
8. CORTICAL ATROPHY table
9. RED FLAGS 🔴
10. AMBER FLAGS 🟡
11. GREEN FLAGS 🟢
12. TOP 5 RECOMMENDED ACTIONS
13. FREESURFER recommendation for exact percentile vs {PATIENT["age"]}yo database
14. COMPARISON NOTE re 2022 MRI (basilar artery, WMH, hippocampus)
DISCLAIMER at end.
ALL FINDINGS: {findings}"""
        resp=client.models.generate_content(model=MODEL,contents=prompt)
        return resp.text
    except Exception as e: return f"[SENTINEL failed: {e}]"
def write_txt(results,sentinel,path,stats):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with open(path,"w",encoding="utf-8") as f:
        f.write("="*70+"\n")
        f.write(f"  BRAIN MRI — {PATIENT[chr(110)+chr(97)+chr(109)+chr(101)]} | Age {PATIENT[chr(97)+chr(103)+chr(101)]}\n")
        f.write(f"  History: {PATIENT[chr(107)+chr(110)+chr(111)+chr(119)+chr(110)+chr(95)+chr(104)+chr(105)+chr(115)+chr(116)+chr(111)+chr(114)+chr(121)]}\n")
        f.write(f"  Generated: {datetime.now().strftime(chr(37)+chr(89)+chr(45)+chr(37)+chr(109)+chr(45)+chr(37)+chr(100)+chr(32)+chr(37)+chr(72)+chr(58)+chr(37)+chr(77)+chr(58)+chr(37)+chr(83))}\n")
        f.write(f"  Series: {stats[chr(115)+chr(101)+chr(114)+chr(105)+chr(101)+chr(115)+chr(95)+chr(111)+chr(107)]}/{stats[chr(115)+chr(101)+chr(114)+chr(105)+chr(101)+chr(115)+chr(95)+chr(116)+chr(111)+chr(116)+chr(97)+chr(108)]} | Total images: {stats[chr(116)+chr(111)+chr(116)+chr(97)+chr(108)+chr(95)+chr(105)+chr(109)+chr(97)+chr(103)+chr(101)+chr(115)]} | Slices to AI: {stats[chr(115)+chr(108)+chr(105)+chr(99)+chr(101)+chr(115)+chr(95)+chr(115)+chr(101)+chr(110)+chr(116)]}\n")
        f.write("="*70+"\n\n"+sentinel+"\n\n")
        for i,r in enumerate(results,1):
            f.write(f"{'─'*60}\n{i}. {r.get(chr(115)+chr(101)+chr(114)+chr(105)+chr(101)+chr(115)+chr(95)+chr(100)+chr(101)+chr(115)+chr(99),'?')} | {r.get(chr(116)+chr(111)+chr(116)+chr(97)+chr(108)+chr(95)+chr(105)+chr(109)+chr(97)+chr(103)+chr(101)+chr(115)+chr(95)+chr(105)+chr(110)+chr(95)+chr(115)+chr(101)+chr(114)+chr(105)+chr(101)+chr(115),'?')} imgs | {r.get(chr(115)+chr(108)+chr(105)+chr(99)+chr(101)+chr(115)+chr(95)+chr(97)+chr(110)+chr(97)+chr(108)+chr(121)+chr(115)+chr(101)+chr(100),'?')} slices sent\n{'─'*60}\n")
            clean={k:v for k,v in r.items() if k not in("series_name","series_desc","agent","role","total_images_in_series","slices_analysed")}
            f.write(json.dumps(clean,indent=2)+"\n\n")
        f.write("="*70+"\n⚕️ AI only — review with neurologist.\n"+"="*70+"\n")
def write_html(results,sentinel,path,stats):
    import html as hl, re
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    def md2h(t):
        o=[]
        for l in t.split("\n"):
            if l.startswith("## "): o.append(f"<h2>{l[3:]}</h2>")
            elif l.startswith("# "): o.append(f"<h1>{l[2:]}</h1>")
            elif l.startswith("| "):
                cells=[c.strip() for c in l.split("|")[1:-1]]
                if all(set(c)<=set("-: ") for c in cells): continue
                tag="th" if not any("<td>" in x for x in o[-5:]) else "td"
                o.append("<tr>"+"".join(f"<{tag}>{hl.escape(c)}</{tag}>" for c in cells)+"</tr>")
            elif l.startswith(("- ","* ")): o.append(f"<li>{hl.escape(l[2:])}</li>")
            elif l.strip()=="---": o.append("<hr>")
            elif l.strip():
                l=re.sub(r"\*\*(.+?)\*\*",r"<strong>\1</strong>",l)
                l=re.sub(r"\*(.+?)\*",r"<em>\1</em>",l)
                o.append(f"<p>{l}</p>")
        return "\n".join(o)
    sh=md2h(sentinel)
    cards=""
    for r in results:
        ok="error" not in r or "raw_analysis" in r
        badge=f'<span class="badge {"ok" if ok else "err"}">{"✓" if ok else "✗"}</span>'
        clean={k:v for k,v in r.items() if k not in("series_name","series_desc","agent","role")}
        rows=""
        for k,v in clean.items():
            if isinstance(v,dict): v=json.dumps(v)
            sv=str(v).upper(); color=""
            if any(x in sv for x in ["SEVERE","CRITICAL","TRUE","SIGNIFICANTLY"]): color="style='color:#f85149;font-weight:bold'"
            elif any(x in sv for x in ["MODERATE","MILD","AMBER"]): color="style='color:#d29922;font-weight:bold'"
            elif any(x in sv for x in ["NORMAL","NONE","FALSE","GREEN"]): color="style='color:#3fb950'"
            rows+=f"<tr><td>{hl.escape(k)}</td><td {color}>{hl.escape(str(v))}</td></tr>"
        cards+=f"<div class='card'><div class='card-header'>{badge} <strong>{hl.escape(r.get(chr(115)+chr(101)+chr(114)+chr(105)+chr(101)+chr(115)+chr(95)+chr(100)+chr(101)+chr(115)+chr(99),'?'))}</strong><span class='meta'>{r.get(chr(115)+chr(101)+chr(114)+chr(105)+chr(101)+chr(115)+chr(95)+chr(110)+chr(97)+chr(109)+chr(101),'?')} | {r.get(chr(116)+chr(111)+chr(116)+chr(97)+chr(108)+chr(95)+chr(105)+chr(109)+chr(97)+chr(103)+chr(101)+chr(115)+chr(95)+chr(105)+chr(110)+chr(95)+chr(115)+chr(101)+chr(114)+chr(105)+chr(101)+chr(115),'?')} imgs | {r.get(chr(115)+chr(108)+chr(105)+chr(99)+chr(101)+chr(115)+chr(95)+chr(97)+chr(110)+chr(97)+chr(108)+chr(121)+chr(115)+chr(101)+chr(100),'?')} slices | Agent: {r.get(chr(97)+chr(103)+chr(101)+chr(110)+chr(116),'?')}</span></div><table>{rows}</table></div>"
    html=f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>Brain MRI — {PATIENT["name"]}</title>
<style>:root{{--bg:#0d1117;--s:#161b22;--b:#30363d;--t:#e6edf3;--m:#8b949e;--a:#58a6ff;--g:#3fb950;--y:#d29922;--r:#f85149}}
*{{box-sizing:border-box;margin:0;padding:0}}body{{background:var(--bg);color:var(--t);font-family:-apple-system,sans-serif;line-height:1.6;padding:2rem}}
.hdr{{background:linear-gradient(135deg,#1a237e,#0d47a1);border-radius:12px;padding:2rem;margin-bottom:2rem}}
.hdr h1{{font-size:1.8rem;color:#fff;margin-bottom:.5rem}}.hdr .m{{color:#90caf9;font-size:.9rem}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:2rem}}
.stat{{background:var(--s);border:1px solid var(--b);border-radius:8px;padding:1rem;text-align:center}}
.stat .v{{font-size:2rem;font-weight:700;color:var(--a)}}.stat .l{{font-size:.8rem;color:var(--m)}}
.sec{{background:var(--s);border:1px solid var(--b);border-radius:12px;padding:1.5rem;margin-bottom:1.5rem}}
h1{{color:var(--a);font-size:1.5rem;margin:1rem 0 .5rem}}h2{{color:var(--a);font-size:1.2rem;margin:1rem 0 .5rem;border-bottom:1px solid var(--b);padding-bottom:.5rem}}
p{{margin:.5rem 0}}li{{margin:.25rem 0 .25rem 1.5rem}}
table{{width:100%;border-collapse:collapse;margin:.5rem 0;font-size:.9rem}}
th{{background:#21262d;color:var(--a);padding:.5rem;text-align:left}}
td{{padding:.4rem .5rem;border-bottom:1px solid var(--b);vertical-align:top;word-break:break-word}}
tr:hover td{{background:#21262d}}.card{{background:#0d1117;border:1px solid var(--b);border-radius:10px;margin-bottom:1rem;overflow:hidden}}
.card-header{{background:var(--s);padding:.75rem 1rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}}
.badge{{padding:.2rem .5rem;border-radius:4px;font-size:.8rem;font-weight:700}}.badge.ok{{background:#1a472a;color:var(--g)}}.badge.err{{background:#4a1a1a;color:var(--r)}}
.meta{{color:var(--m);font-size:.8rem;margin-left:auto}}.card table td:first-child{{color:var(--m);width:35%;font-size:.85rem}}
hr{{border:none;border-top:1px solid var(--b);margin:1rem 0}}.disc{{background:#1a0a0a;border:1px solid #f8514933;border-radius:8px;padding:1rem;color:var(--r);font-size:.85rem;margin-top:2rem}}
strong{{color:#f0f6fc}}em{{color:var(--m)}}</style></head><body>
<div class="hdr"><h1>🧠 Brain MRI Analysis Report</h1>
<div class="m"><strong>{PATIENT["name"]}</strong> | DOB: {PATIENT["dob"]} | Age: {PATIENT["age"]} | {PATIENT["sex"]}<br>
Scan: {PATIENT["scan_date"]} | {PATIENT["facility"]}<br>History: {PATIENT["known_history"]}<br>
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | AI: Google {MODEL}</div></div>
<div class="stats">
<div class="stat"><div class="v">{stats["series_ok"]}/{stats["series_total"]}</div><div class="l">Series Analysed</div></div>
<div class="stat"><div class="v">{stats["total_images"]}</div><div class="l">Total DICOM Images</div></div>
<div class="stat"><div class="v">{stats["slices_sent"]}</div><div class="l">Slices Sent to AI</div></div>
<div class="stat"><div class="v">{stats["series_total"]}</div><div class="l">Priority Series Found</div></div>
</div>
<div class="sec"><h2>🛡️ SENTINEL Master Report</h2>{sh}</div>
<div class="sec"><h2>🔬 Detailed Per-Series Findings</h2>{cards}</div>
<div class="disc">⚕️ <strong>CLINICAL DISCLAIMER:</strong> AI analysis only. Review with qualified neurologist before any clinical decision.</div>
</body></html>"""
    with open(path,"w",encoding="utf-8") as f: f.write(html)
def main():
    print(f"\n{'='*60}\n  🧠 HEALTH DIGITAL WORKFORCE\n  {PATIENT[chr(110)+chr(97)+chr(109)+chr(101)]} | Age {PATIENT[chr(97)+chr(103)+chr(101)]} | {PATIENT[chr(107)+chr(110)+chr(111)+chr(119)+chr(110)+chr(95)+chr(104)+chr(105)+chr(115)+chr(116)+chr(111)+chr(114)+chr(121)]}\n{'='*60}\n")
    client=setup()
    print("\n📂 Scanning DICOM series...")
    series_list=discover_series()
    if not series_list: print("No priority series found."); sys.exit(0)
    print(f"\n✓ {len(series_list)} series found:")
    for s in series_list: print(f"  {s[chr(115)+chr(101)+chr(95)+chr(110)+chr(97)+chr(109)+chr(101)]} | {s[chr(100)+chr(101)+chr(115)+chr(99)]} | {s[chr(110)+chr(95)+chr(105)+chr(109)+chr(97)+chr(103)+chr(101)+chr(115)]} imgs → {s[chr(97)+chr(103)+chr(101)+chr(110)+chr(116)]}")
    print()
    results=[]; total_images=sum(s[chr(110)+chr(95)+chr(105)+chr(109)+chr(97)+chr(103)+chr(101)+chr(115)] for s in series_list); slices_sent=0
    for s in series_list:
        print(f"🔬 {s[chr(115)+chr(101)+chr(95)+chr(110)+chr(97)+chr(109)+chr(101)]} {s[chr(100)+chr(101)+chr(115)+chr(99)]} ({s[chr(110)+chr(95)+chr(105)+chr(109)+chr(97)+chr(103)+chr(101)+chr(115)]} images)...")
        r=analyse(client,s); results.append(r); slices_sent+=r.get(chr(115)+chr(108)+chr(105)+chr(99)+chr(101)+chr(115)+chr(95)+chr(97)+chr(110)+chr(97)+chr(108)+chr(121)+chr(115)+chr(101)+chr(100),0)
        ok="error" not in r or "raw_analysis" in r
        print(f"  {'✓' if ok else '✗'} Done — {r.get(chr(115)+chr(108)+chr(105)+chr(99)+chr(101)+chr(115)+chr(95)+chr(97)+chr(110)+chr(97)+chr(108)+chr(121)+chr(115)+chr(101)+chr(100),0)} slices sent")
        time.sleep(2)
    stats=dict(series_ok=sum(1 for r in results if "error" not in r or "raw_analysis" in r),series_total=len(results),total_images=total_images,slices_sent=slices_sent)
    print("\n🛡️  SENTINEL compiling...")
    master=sentinel_summary(client,results)
    write_txt(results,master,OUTPUT_TXT,stats)
    write_html(results,master,OUTPUT_HTML,stats)
    print(master[:2000])
    print(f"\n✅ TXT:  {OUTPUT_TXT}\n   HTML: {OUTPUT_HTML}\n   Stats: {stats}\n")
if __name__=="__main__": main()
