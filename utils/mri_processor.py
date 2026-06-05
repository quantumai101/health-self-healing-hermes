import pydicom
import os
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()
MRI_PATH = os.getenv("MRI_LOCAL_PATH", r"C:\CMRI Brain 5Jan2024")

def triage_and_group_mri():
    """
    Groups DICOM files by Series and automatically selects the highest
    priority scans for PROMETHEUS to analyze first.
    """
    search_path = Path(MRI_PATH)
    series_map = defaultdict(list)
    
    # 1. Scan and Group by Series
    for dcm_file in search_path.rglob("*"):
        if dcm_file.is_file() and dcm_file.suffix.lower() in [".dcm", ".ima", ""]:
            try:
                ds = pydicom.dcmread(str(dcm_file), stop_before_pixels=True)
                desc = ds.get("SeriesDescription", "Unknown_Series")
                series_map[desc].append(str(dcm_file))
            except:
                continue

    # 2. Scan Agent Decision Logic (Ranking)
    # Priority 1: FLAIR (Microvascular/Ischemia)
    # Priority 2: T1 (Grey/White Matter Volume)
    # Priority 3: T2 (General Structural)
    
    analysis_queue = []
    
    # Priority keywords in order of medical importance for your queries
    priorities = ["FLAIR", "T1", "T2", "AXIAL"]
    
    for key in priorities:
        for series_name, files in series_map.items():
            if key in series_name.upper() and series_name not in [p['name'] for p in analysis_queue]:
                analysis_queue.append({
                    "name": series_name,
                    "priority": len(priorities) - priorities.index(key),
                    "file_count": len(files),
                    "sample_path": files[0], # First file for PROMETHEUS to start with
                    "all_files": files
                })

    return {
        "full_series_map": dict(series_map),
        "recommended_queue": sorted(analysis_queue, key=lambda x: x['priority'], reverse=True)
    }

if __name__ == "__main__":
    scan_results = triage_and_group_mri()
    print(f"--- Scan Agent Decision Report ---")
    for item in scan_results['recommended_queue']:
        print(f"Priority {item['priority']}: {item['name']} ({item['file_count']} files)")
        print(f"   -> Passing to PROMETHEUS first.")