import os
import re
import mlflow

# 1. Configure the Local SQLite Tracking Database
# Ensure this matches your specific DB path
DB_PATH = r"sqlite:///I:\MRA Brian 28May2022\brain_mlflow.db"
mlflow.set_tracking_uri(DB_PATH)

# 2. Define or Get the Experiment
EXPERIMENT_NAME = "Brian MRI Analysis Report"
mlflow.set_experiment(EXPERIMENT_NAME)

# Path to your text report
REPORT_PATH = r"I:\MRA Brian 28May2022\MRA_Analysis_Report.txt"

def parse_and_log_report(file_path):
    if not os.path.exists(file_path):
        print(f"Error: Report file not found at {file_path}")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    print("Starting MLflow logging run...")
    
    # Start a tracking run named after the specific MRI scan date
    with mlflow.start_run(run_name="MRA_Scan_28May2022") as run:
        
        # --- LOG SYSTEM TAGS ---
        mlflow.set_tag("Pipeline_Agent", "Hermes MRA Analysis Agent")
        mlflow.set_tag("Scan_Date", "2022-05-28")
        
        # --- PARSE AND LOG CLINICAL PARAMETERS (Text Items) ---
        # Look for Patient Finding metrics
        dolicho_match = re.search(r"Dolichoectasia is a ([^\.]+)", content)
        if dolicho_match:
            mlflow.log_param("Finding_Dolichoectasia", dolicho_match.group(1).strip())
            
        tortuosity_match = re.search(r"([^\.]+ tortuosity\.)", content)
        if tortuosity_match:
            mlflow.log_param("Finding_Tortuosity", tortuosity_match.group(1).strip())

        # --- PARSE AND LOG BRAIN METRICS (Numerical Items) ---
        # Regular expressions to hunt down percentages and ratios in the report text
        gm_match = re.search(r"GM\s*=\s*([\d\.]+)%", content)
        wm_match = re.search(r"WM\s*=\s*([\d\.]+)%", content)
        csf_match = re.search(r"CSF\s*=\s*([\d\.]+)%", content)
        wmh_match = re.search(r"WMH\s*=\s*([\d\.]+)%", content)
        mta_l_match = re.search(r"MTA L\s*=\s*([\d\.]+)", content)
        mta_r_match = re.search(r"MTA R\s*=\s*([\d\.]+)", content)
        
        if gm_match:
            mlflow.log_metric("Volume_Gray_Matter_Pct", float(gm_match.group(1)))
        if wm_match:
            mlflow.log_metric("Volume_White_Matter_Pct", float(wm_match.group(1)))
        if csf_match:
            mlflow.log_metric("Volume_CSF_Pct", float(csf_match.group(1)))
        if wmh_match:
            mlflow.log_metric("Volume_White_Matter_Hyperintensities_Pct", float(wmh_match.group(1)))
        if mta_l_match:
            mlflow.log_metric("MTA_Scale_Left", float(mta_l_match.group(1)))
        if mta_r_match:
            mlflow.log_metric("MTA_Scale_Right", float(mta_r_match.group(1)))

        # Log structural metadata strings as params
        confidence_match = re.search(r"Confidence:\s*(\w+)", content)
        if confidence_match:
            mlflow.log_param("Model_Confidence_Level", confidence_match.group(1))

        # --- LOG WHOLE RAW TEXT AS AN ARTIFACT ---
        # This populates the Right Panel file explorer inside the run view
        temp_text_path = "Full_MRA_Clinical_Report.txt"
        with open(temp_text_path, "w", encoding="utf-8") as temp_f:
            temp_f.write(content)
        mlflow.log_artifact(temp_text_path, artifact_path="clinical_outputs")
        os.remove(temp_text_path)

        print(f"Successfully populated MLflow Interface! Run ID: {run.info.run_id}")

if __name__ == "__main__":
    parse_and_log_report(REPORT_PATH)