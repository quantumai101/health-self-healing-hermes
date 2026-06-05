import os
import sys
from pathlib import Path
import pydicom

# The path based directly on your Windows Explorer layout
CTCA_ROOT = r"I:\CTCA Heart Scan DVD 20April2026"
DICOM_DIR = Path(CTCA_ROOT) / "DICOM"

def run_diagnostic_discovery():
    print("=" * 75)
    print(" 🫀  CTCA DISC DIAGNOSTIC & DATA DISCOVERY TOOL")
    print("=" * 75)
    print(f"Target Root: {CTCA_ROOT}")
    print(f"Scanning DICOM Folder: {DICOM_DIR}\n")

    if not DICOM_DIR.exists():
        print(f"❌ ERROR: The path '{DICOM_DIR}' cannot be reached.")
        print("Please verify the DVD is fully loaded or that the drive letter 'I:' is correct.")
        return

    # Phase 1: Scan for series directories
    all_dirs = sorted([d for d in DICOM_DIR.rglob('*') if d.is_dir()])
    discovered_series = []
    total_files_found = 0

    print("🔍 Scanning directory tree for medical image series...")
    
    for folder in all_dirs:
        # Filter files to avoid metadata/viewers
        valid_files = [
            f for f in sorted(folder.iterdir()) 
            if f.is_file() and f.suffix.lower() not in {".zip", ".gz", ".txt", ".xml", ".json", ".dir"}
        ]
        
        if not valid_files:
            continue
            
        total_files_found += len(valid_files)
        
        # Read the internal DICOM metadata headers from a sample slice (the middle slice)
        sample_file = valid_files[len(valid_files) // 2]
        try:
            ds = pydicom.dcmread(str(sample_file), stop_before_pixels=True)
            
            # Extract clinical parameters from the header tags
            patient_name = str(getattr(ds, "PatientName", "Unknown Patient"))
            patient_id = str(getattr(ds, "PatientID", "Unknown ID"))
            series_desc = str(getattr(ds, "SeriesDescription", "No Description Found")).strip()
            modality = str(getattr(ds, "Modality", "CT"))
            scan_date = str(getattr(ds, "StudyDate", "Unknown Date"))
            manufacturer = str(getattr(ds, "Manufacturer", "Unknown Manufacturer"))
            
            discovered_series.append({
                "folder_path": folder,
                "folder_name": folder.name,
                "description": series_desc,
                "count": len(valid_files),
                "patient_name": patient_name,
                "patient_id": patient_id,
                "modality": modality,
                "scan_date": scan_date,
                "manufacturer": manufacturer
            })
        except Exception as e:
            # Not a valid DICOM file or header unreadable
            continue

    if not discovered_series:
        print("❌ No valid DICOM metadata series could be parsed.")
        return

    # Phase 2: Report global demographic metadata from the first clean series found
    meta = discovered_series[0]
    # Clean up standard DICOM date formatting (YYYYMMDD to readable)
    s_date = meta['scan_date']
    if len(s_date) == 8:
        s_date = f"{s_date[6:8]}/{s_date[4:6]}/{s_date[0:4]}"

    print("\n" + "="*50)
    print("📋 VERIFIED INTERNAL PATIENT MANIFEST")
    print("="*50)
    print(f"  Patient Name:     {meta['patient_name']}")
    print(f"  Patient ID:       {meta['patient_id']}")
    print(f"  Scan Modality:    {meta['modality']} (Computed Tomography)")
    print(f"  Acquisition Date: {s_date}")
    print(f"  Scanner Hardware: {meta['manufacturer']}")
    print(f"  Total Files:      {total_files_found} files detected on media")
    print("="*50 + "\n")

    # Phase 3: Print the structural mapping table
    print("📂 DETECTED CARDIAC SERIES MAPPING:")
    print(f"{'Folder':<12} | {'Series Description (DICOM Header)':<35} | {'Slices Found'}")
    print("-" * 75)
    
    for s in discovered_series:
        print(f"{s['folder_name']:<12} | {s['description']:<35} | {s['count']} images")
        
    print("-" * 75)
    print("\n✅ Verification complete. Your data drive is responsive and ready.")

if __name__ == "__main__":
    run_diagnostic_discovery()