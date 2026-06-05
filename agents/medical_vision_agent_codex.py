import os
import io
import base64
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from openai import OpenAI
import pydicom
from PIL import Image
import numpy as np

def convert_dicom_to_base64_png(file_path):
    """Safely reads raw DICOM image arrays and converts them to valid PNG Base64 strings."""
    try:
        ds = pydicom.dcmread(file_path)
        pixel_array = ds.pixel_array
        
        # Normalize pixel intensities smoothly
        pixel_array = pixel_array.astype(float)
        max_val = pixel_array.max()
        rescaled_image = (np.maximum(pixel_array, 0) / (max_val if max_val > 0 else 1.0)) * 255.0
        final_image = np.uint8(rescaled_image)
        
        img = Image.fromarray(final_image)
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        return None

def process_single_frame(index, file_name, folder_path, client):
    """Worker task that handles a single frame inference transaction."""
    file_path = os.path.join(folder_path, file_name)
    base64_image = convert_dicom_to_base64_png(file_path)
    
    if not base64_image:
        return index, file_name, f"⚠️ Frame {file_name}: Failed to extract or decode DICOM matrix data."

    # Strict geometric prompt to strip defensive disclaimers and force structure tracking
    clinical_prompt = (
        f"This is slice element {file_name} from a sequential cross-sectional dataset. "
        "Provide a strict geometric and structural description of the image layout. "
        "Describe the orientation of high-contrast boundaries, spatial distribution of shapes, "
        "and visible gray-scale variations. Avoid generic medical advice or disclaimers, "
        "and focus purely on the visual data presented."
    )

    try:
        response = client.chat.completions.create(
            model="llava:7b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": clinical_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1,
            stream=False
        )
        analysis = response.choices[0].message.content
        return index, file_name, analysis
    except Exception as e:
        return index, file_name, f"❌ Error analyzing frame {file_name}: {e}"

def main():
    load_dotenv()

    raw_path = os.getenv("CTCA_LOCAL_PATH")
    folder_path = os.path.normpath(raw_path) if raw_path else None
    
    print("=" * 70)
    print("⚡ PARALLEL HIGH-VELOCITY DICOM VISION PIPELINE")
    print("=" * 70)
    print(f"📂 Target: {folder_path}")
    
    if not folder_path or not os.path.exists(folder_path):
        print("❌ Error: Target folder path not found.")
        return

    # Updated log target filename to isolate from previous slow/locked script records
    report_path = os.path.join(os.getcwd(), "parallel_pipeline_report.txt")

    try:
        all_files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f)) and f.isdigit()]
        all_files.sort(key=int)
        
        if not all_files:
            print("❌ Error: No raw medical elements found.")
            return
            
        # STRUCTURAL SAMPLING RATE
        # Step Size 40 windows the massive 2849 set down to roughly 71 key frame waypoints
        STEP_SIZE = 40 
        sampled_files = all_files[::STEP_SIZE]
            
        print(f"📋 Total Dataset: {len(all_files)} elements.")
        print(f"🚀 High-Speed Queue: {len(sampled_files)} keyframes targeted (Step Size: {STEP_SIZE}).")
        print("⚡ Thread pool processing initialized...")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error indexing files: {e}")
        return

    try:
        client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama-local-token")
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return

    compiled_results = {}

    start_time = time.time()
    print("▶️ Processing batch arrays concurrently. Standby...")
    
    # 3 worker threads keep your RAM safe while feeding Ollama efficiently
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(process_single_frame, idx, fname, folder_path, client): fname 
            for idx, fname in enumerate(sampled_files, start=1)
        }
        
        for future in as_completed(futures):
            idx, fname, result_text = future.result()
            compiled_results[idx] = {"name": fname, "content": result_text}
            print(f"✅ Finished Processing Frame [{idx}/{len(sampled_files)}]: Element -> {fname}")

    # Write cleanly compiled, numerically sorted results to the fresh log file
    with open(report_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"=== HERMES CTCA HIGH-SPEED PARALLEL REPORT ===\n")
        log_file.write(f"Total Keyframes Processed: {len(sampled_files)}\n")
        log_file.write("=" * 70 + "\n\n")
        
        for idx in sorted(compiled_results.keys()):
            frame_data = compiled_results[idx]
            log_file.write(f"📸 FRAME KEY {idx}: Element {frame_data['name']}\n")
            log_file.write("-" * 50 + "\n")
            log_file.write(f"{frame_data['content']}\n")
            log_file.write("=" * 50 + "\n\n")

    elapsed_time = time.time() - start_time
    print("\n🏁 HIGH-SPEED PIPELINE RUN CONCLUDED SUCCESSFULLY.")
    print(f"⏱️ Total Execution Time: {elapsed_time / 60:.1f} minutes.")
    print(f"📂 Clean structured report built here: {report_path}")
    print("=" * 70)

if __name__ == "__main__":
    main()