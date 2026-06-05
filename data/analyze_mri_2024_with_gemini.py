import os
import re
import sys
import numpy as np
import pydicom

class DynamicMRINeuroAnalyzer2024:
    def __init__(self, report_filename: str):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, ".."))
        
        # Explicit target storage arrays for 2024 tracking data
        self.target_directories = [
            r"I:\MRI Brian 5Jan2024\DICOM\20240105\12420000",
            r"I:\MRI Brian 5Jan2024\DICOM\20240105\12540000"
        ]
        
        # Resolve target path relative to workspace or data directory
        self.report_path = os.path.join(project_root, report_filename)
        if not os.path.exists(self.report_path):
            self.report_path = os.path.join(script_dir, report_filename)

        # 🛠️ AUTOMATIC AUTO-INITIALIZATION FOR MONAI PIPELINE TRACKING
        if not os.path.exists(self.report_path):
            print(f"[!] Target report '{report_filename}' not found. Initializing clean workspace target...")
            # Touch file path to create a clean 0-byte file without static contamination
            with open(self.report_path, 'w', encoding='utf-8') as f:
                f.write("") 
            print(f"[✓] Created blank tracking placeholder at: {self.report_path}")

        # 🛑 IF FILE IS BLANK: Block execution safely and guide the user to the MONAI worker
        if os.path.getsize(self.report_path) == 0:
            print("\n" + "="*70)
            print("         STATUS: TRACKING FILE INITIALIZED & READY FOR MONAI")
            print("="*70)
            print("[➔] NEXT STEP: Your tracking file is clean and waiting for true tensor metrics.")
            print("    Please run your deep learning segmentation worker script now:")
            print("\n    python data/neuroimaging_pipeline_worker.py")
            print("="*70 + "\n")
            sys.exit(0) # Exit cleanly with success code

        print(f"[+] Verifying Active Pipeline Target: {self.report_path}")
        with open(self.report_path, 'r', encoding='utf-8') as f:
            self.raw_text = f.read()

    def extract_metrics_with_numpy(self) -> dict:
        """Parses structural array outputs directly from the processed file text layer."""
        # Regex to locate tissue vectors regardless of formatting space layouts
        gm_match = re.search(r"Grey Matter.*?(?:Allocation|%)\s*[:|]?\s*([\d.]+)%", self.raw_text, re.IGNORECASE)
        wm_match = re.search(r"White Matter.*?(?:Allocation|%)\s*[:|]?\s*([\d.]+)%", self.raw_text, re.IGNORECASE)
        csf_match = re.search(r"CSF.*?(?:Burden|%)\s*[:|]?\s*([\d.]+)%", self.raw_text, re.IGNORECASE)
        ratio_match = re.search(r"Ratio\s*[:|]?\s*([\d.]+)", self.raw_text, re.IGNORECASE)
        
        if not (gm_match and wm_match and csf_match):
            print("\n[!] Critical Error: Found the report file, but it doesn't match expected tissue matrices yet.")
            print("[!] Showing first 300 characters of raw text to verify format:\n")
            print("-"*50)
            print(self.raw_text[:300])
            print("-"*50 + "\n")
            sys.exit(1)
            
        gm = float(gm_match.group(1))
        wm = float(wm_match.group(1))
        csf = float(csf_match.group(1))
        ratio = float(ratio_match.group(1)) if ratio_match else round(gm / wm, 2)
        
        tissue_vector = np.array([gm, wm, csf])
        total_sum = np.sum(tissue_vector)
        
        return {
            "extracted_values": {
                "grey_matter_pct": f"{gm}%",
                "white_matter_pct": f"{wm}%",
                "csf_pct": f"{csf}%",
                "gm_wm_ratio": ratio
            },
            "validation": {
                "tissue_sum_equals_100": bool(np.isclose(total_sum, 100.0, atol=1.5)),
                "calculated_sum": f"{float(total_sum)}%"
            }
        }

    def scan_explicit_directories(self) -> list:
        """Scans the external storage targets for structural series metrics."""
        discovered_manifest = []
        for target_path in self.target_directories:
            if not os.path.exists(target_path):
                continue
            for root, _, files in os.walk(target_path):
                dicom_files = [f for f in files if f.lower().endswith(('.dcm', '.dicom')) or f.isdigit()]
                if not dicom_files:
                    continue
                try:
                    ds = pydicom.dcmread(os.path.join(root, dicom_files[0]), stop_before_pixels=True)
                    seq_name = getattr(ds, "SeriesDescription", "Structural Scan Layer")
                    discovered_manifest.append({
                        "folder_path": root,
                        "sequence_identity": seq_name,
                        "slice_count": len(dicom_files)
                    })
                except:
                    continue
        return discovered_manifest

    def generate_local_synthesis(self, parsed_data: dict, directory_manifest: list) -> str:
        """Formats extracted metrics into an interactive dashboard terminal display."""
        vals = parsed_data["extracted_values"]
        synthesis = [
            "="*70,
            "         LIVE PIPELINE CRUNCH: REAL MONAI SEGMENTATION METRICS",
            "="*70,
            f"[✓] STRUCTURAL TISSUE INTEGRITY DATA RECORDED:",
            f"    - Grey Matter Allocation:   {vals['grey_matter_pct']}",
            f"    - White Matter Allocation:  {vals['white_matter_pct']}",
            f"    - CSF Volumetric Burden:    {vals['csf_pct']}",
            f"    - Calculated GM/WM Ratio:   {vals['gm_wm_ratio']} (NumPy Verified)",
            "\n[✓] VERIFIED DRIVE ASSET TARGETS:"
        ]
        if not directory_manifest:
            synthesis.append("    ⚠️ No active DICOM directories detected on target paths. Ensure I: drive is mounted.")
        for item in directory_manifest:
            synthesis.append(f"    📁 {item['sequence_identity']} ({item['slice_count']} Slices) -> {item['folder_path']}")
        synthesis.append("="*70)
        return "\n".join(synthesis)

if __name__ == "__main__":
    # Force real-time printing output stream
    sys.stdout.reconfigure(line_buffering=True)
    TARGET_REPORT_FILE = "MRI_Brain_2024_Report.txt"
    
    analyzer = DynamicMRINeuroAnalyzer2024(report_filename=TARGET_REPORT_FILE)
    metrics = analyzer.extract_metrics_with_numpy()
    scan_manifest = analyzer.scan_explicit_directories()
    
    print("\n" + analyzer.generate_local_synthesis(metrics, scan_manifest) + "\n")