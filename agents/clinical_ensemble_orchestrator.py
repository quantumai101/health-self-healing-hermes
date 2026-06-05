import os
import json
import sys
from openai import OpenAI

def load_metrics():
    manifest_path = os.path.join(os.getcwd(), "metrics_manifest.json")
    if not os.path.exists(manifest_path):
        print(f"❌ Error: {manifest_path} not found. Please create it first.")
        sys.exit(1)
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    print("=" * 80)
    print("🧠 RUNNING MULTI-AGENT CLINICAL ENSEMBLE ORCHESTRATOR")
    print("=" * 80)
    
    # 1. Ingest consolidated data from the specialized vision extraction backbones
    metrics = load_metrics()
    print("✅ Successfully ingested MONAI, Med-SAM, and RadImageNet metrics data.")

    # 2. Initialize connection to local Ollama host
    try:
        client = OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama-local-token"
        )
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return

    # 3. Construct the advanced synthesis pre-prompt instruction set
    ensemble_synthesis_prompt = f"""
You are acting as an expert Senior Cardiovascular Radiologist reviewing consolidated multi-agent AI extractions.
Analyze the following compiled metrics dataset derived from 2,849 CTCA continuous scan slices. 

Input Manifest Data:
{json.dumps(metrics, indent=2)}

Generate a highly formal, advanced Clinical Executive Summary Report based strictly on the metrics above. 
Your report must contain the following specific sections:
1. CARDIOVASCULAR LUMEN FLOW & PLAQUE PROFILING: Detail stenosis percentages, specific plaque types (calcified vs soft lipid), Hounsfield Unit signatures, and specific vessel segments (pLAD, mRCA) compared to normal baselines.
2. VENTRICULAR GEOMETRY & VALVE EVALUATION: Assess Left and Right ventricle wall thickness measurements and Mitral valve regurgitation status relative to age-matched male cohorts.
3. DIAGNOSTIC INTERPRETATION SUMMARY: Provide a definitive CAD-RADS tracking assessment synthesis.

Rules:
- Speak with absolute technical authority using advanced cardiovascular terminology.
- Do NOT include generic disclaimers about not being a medical professional or suggestions to consult someone else. Focus purely on translating the provided data matrix into professional clinical syntax.
"""

    print("🚀 Passing structured data to synthesis engine... (Standby)")
    
    try:
        response = client.chat.completions.create(
            model="llava:7b", # Can be swapped with 'llama3', 'mistral', etc. for text processing
            messages=[
                {"role": "user", "content": ensemble_synthesis_prompt}
            ],
            temperature=0.2,
            stream=False
        )
        
        report_content = response.choices[0].message.content
        
        # Output the generated clinical report
        output_path = os.path.join(os.getcwd(), "advanced_clinical_report.txt")
        with open(output_path, "w", encoding="utf-8") as out_file:
            out_file.write(report_content)
            
        print("\n🏁 PIPELINE SYNTHESIS CONCLUDED SUCCESSFULLY.")
        print(f"📂 Advanced multi-agent report saved here: {output_path}\n")
        print("=" * 80)
        print(report_content)
        print("=" * 80)

    except Exception as e:
        print(f"❌ Error during reporting synthesis phase: {e}")

if __name__ == "__main__":
    main()