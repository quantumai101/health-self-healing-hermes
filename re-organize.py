import os
import shutil

def safe_restructure():
    # 1. Define folder structure
    folders = ['core', 'agents', 'pages', 'utils', 'data', 'tests']
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        # Create __init__.py for each
        with open(os.path.join(folder, '__init__.py'), 'w') as f:
            pass

    # 2. Strict File Mapping (Only moves files if they exist in the root)
    mapping = {
        'agents': ['axiom.py', 'compliance.py', 'news.py', 'nexus.py', 'nova.py', 'prometheus.py', 'sentinel.py'],
        'core': ['config.py', 'session.py', 'db.py', 'gemini.py', 'chat.py'],
        'data': ['medical_kb.py', 'synthetic_patients.py'],
        'pages': ['app.py', 'dashboard.py', 'ehr_summarizer.py', 'imaging.py'],
        'tests': ['test_agents.py', 'test_gemini_fallback.py', 'test_medical_kb.py']
    }

    # 3. Move only from root to target
    for folder, files in mapping.items():
        for filename in files:
            if os.path.isfile(filename): # ONLY looks in the root folder
                shutil.move(filename, os.path.join(folder, filename))
                print(f"Moved {filename} to {folder}/")

    print("\nCleanup and restructure complete!")

if __name__ == "__main__":
    safe_restructure()