import pydicom
import os
import json
from pathlib import Path

def extract_mri_metadata(directory_path):
    """
    Scans a directory (like your F: drive) for DICOM files 
    and extracts key clinical metadata for AI analysis.
    """
    extracted_data = []
    path = Path(directory_path)

    # Search for common DICOM extensions
    for dcm_file in path.rglob("*"):
        if dcm_file.suffix.lower() in [".dcm", ".ima", ""]:
            try:
                # stop_before_pixels=True makes this 100x faster for indexing
                ds = pydicom.dcmread(str(dcm_file), stop_before_pixels=True)
                
                # Basic check to ensure it's a valid medical file
                if "Modality" not in ds: continue

                info = {
                    "file": str(dcm_file.name),
                    "modality": ds.get("Modality", "N/A"),
                    "description": ds.get("SeriesDescription", "N/A"),
                    "study_date": ds.get("StudyDate", "N/A"),
                    "body_part": ds.get("BodyPartExamined", "N/A"),
                    # Technical parameters for Grey/White matter analysis
                    "echo_time": ds.get("EchoTime", "N/A"),
                    "repetition_time": ds.get("RepetitionTime", "N/A"),
                    "slice_thickness": ds.get("SliceThickness", "N/A"),
                    "pixel_spacing": str(ds.get("PixelSpacing", "N/A"))
                }
                extracted_data.append(info)
            except Exception:
                continue # Skip non-DICOM or corrupted files

    return extracted_data

# Example usage for your DVD drive
results = extract_mri_metadata("F:\\DICOM")
print(json.dumps(results[:3], indent=2)) # View first 3 results