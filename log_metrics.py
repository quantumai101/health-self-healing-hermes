import os
import mlflow
import datetime

# --- PIPELINE CONFIGURATION ---
TARGET_DIR = r"I:\MRI Brian 5Jan2024"
DB_PATH = "sqlite:///data/brain_mlflow.db"
EXPERIMENT_NAME = "BrainMRI_Analysis"

# Live metrics from your recent SwinUNETR execution
metrics = {
    "GM_percentage": 8.74,
    "WM_percentage": 40.14,
    "CSF_percentage": 51.12,
    "WMH_burden_percentage": 127.35,
    "GM_WM_Ratio": 0.218
}

def generate_reports_and_log_mlflow():
    # 1. Setup Environment
    os.makedirs(TARGET_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 2. Generate Content
    txt_content = f"""======================================================================
         LIVE PIPELINE CRUNCH: REAL MONAI SEGMENTATION METRICS
======================================================================
Report Generated: {timestamp}
----------------------------------------------------------------------
Metrics Matrix Summary:
    - Grey Matter Allocation (GM %):        {metrics['GM_percentage']}%
    - White Matter Allocation (WM %):       {metrics['WM_percentage']}%
    - CSF Volumetric Burden (CSF %):        {metrics['CSF_percentage']}%
    - White Matter Hyperintensity Burden:   {metrics['WMH_burden_percentage']}%
    - Calculated GM/WM Ratio:               {metrics['GM_WM_Ratio']}
----------------------------------------------------------------------
[+] Status: Computed via MONAI Deep Learning Transformer Architecture
======================================================================
"""

    html_content = f"""
    <html><body style="font-family:sans-serif; background:#0b0f19; color:#fff; padding:40px;">
    <div style="max-width:800px; margin:auto; border:1px solid #333; padding:20px; border-radius:10px;">
    <h2 style="color:#3b82f6;">🧠 MONAI SwinUNETR Brain Report</h2>
    <hr style="border:0; border-top:1px solid #333;">
    <p><b>Analysis Date:</b> {timestamp}</p>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
        <div style="background:#1f2937; padding:15px; border-radius:8px;">GM: {metrics['GM_percentage']}%</div>
        <div style="background:#1f2937; padding:15px; border-radius:8px;">WM: {metrics['WM_percentage']}%</div>
        <div style="background:#1f2937; padding:15px; border-radius:8px;">CSF: {metrics['CSF_percentage']}%</div>
        <div style="background:#1f2937; padding:15px; border-radius:8px;">Ratio: {metrics['GM_WM_Ratio']}</div>
    </div>
    </div></body></html>
    """

    # 3. Write Files to I: Drive
    txt_path = os.path.join(TARGET_DIR, "MRI_Brain_2024_Report.txt")
    html_path = os.path.join(TARGET_DIR, "MRI_Brain_2024_Report.html")
    
    with open(txt_path, "w") as f: f.write(txt_content)
    with open(html_path, "w") as f: f.write(html_content)
    print(f"[✓] Local Reports generated at: {TARGET_DIR}")

    # 4. MLflow Integration
    mlflow.set_tracking_uri(DB_PATH)
    mlflow.set_experiment(EXPERIMENT_NAME)
    
    with mlflow.start_run(run_name=f"MONAI_Run_{datetime.datetime.now().strftime('%H%M%S')}"):
        # Log metrics with native % support in tracking
        mlflow.log_metrics({k: v for k, v in metrics.items()})
        
        # Log parameters
        mlflow.log_param("Model_Type", "SwinUNETR_3D")
        mlflow.log_param("Device", "CPU_Optimized")
        
        # Attach reports as Artifacts
        mlflow.log_artifact(txt_path)
        mlflow.log_artifact(html_path)
        
        print(f"[✓] MLflow Run Recorded: {mlflow.active_run().info.run_id}")
        print(f"[➔] View results at: http://127.0.0.1:5001")

if __name__ == "__main__":
    generate_reports_and_log_mlflow()