import os
import sys
import logging
import json
import asyncio
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Any
from pydantic import Field, ValidationError, confloat, SecretStr, BaseModel, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from google import genai
from google.genai import types as gtypes

# ── Configuration Management ────────────────────────────────────────────────
class Settings(BaseSettings):
    """Application configuration using Pydantic Settings for environment validation."""
    gemini_api_key: SecretStr
    model_name: str = "gemini-2.0-flash"
    manifest_path: str = "psa_metrics_manifest.json"
    system_prompt_path: str = "config/system_prompt_v1.txt"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

try:
    settings = Settings()
except ValidationError as e:
    print(f"Configuration error: {e}")
    sys.exit(1)

# ── Logging Configuration ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PSAOrchestrator")

# ── Global Engines ──────────────────────────────────────────────────────────
analyzer_engine = AnalyzerEngine()
anonymizer_engine = AnonymizerEngine()

# Dynamic ThreadPoolExecutor: Scaled for high-concurrency medical workloads
# Monitoring: In production, consider wrapping this in a custom executor that tracks queue depth
executor = ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 1) + 4))

# ── Pydantic Models ─────────────────────────────────────────────────────────
class PSAEntry(BaseModel):
    date: str
    total_psa: confloat(ge=0.0, le=1000.0)
    free_psa: Optional[confloat(ge=0.0, le=1000.0)] = None
    free_pct: Optional[confloat(ge=0.0, le=100.0)] = None

class LabResults(BaseModel):
    crp_feb26: confloat(ge=0.0, le=500.0)
    iron_feb26: confloat(ge=0.0, le=500.0)
    iron_saturation_pct: confloat(ge=0.0, le=100.0)
    ferritin: confloat(ge=0.0, le=5000.0)
    ldl: confloat(ge=0.0, le=500.0)
    egfr: confloat(ge=0.0, le=200.0)
    creatinine: confloat(ge=0.0, le=20.0)

class ClinicalManifest(BaseModel):
    version: str = Field(alias="_version")
    patient_metadata: Dict[str, Any]
    psa_history: List[PSAEntry]
    labs: LabResults
    ctca: Dict[str, Any]
    pending: List[str]

class ClinicalAssessment(BaseModel):
    """Structured output schema to prevent LLM hallucinations."""
    assessment: str
    recommendation: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    disclaimer: str = "This is an AI-generated decision support tool and must be reviewed by a qualified clinician."
    last_updated: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

# ── PHI Redaction Logic ─────────────────────────────────────────────────────
def redact_phi_sync(data: Dict[str, Any]) -> str:
    """
    Synchronous redaction logic. 
    Raises Exception on failure to prevent downstream processing of unredacted PHI.
    """
    try:
        text_data = json.dumps(data)
        results = analyzer_engine.analyze(
            text=text_data, 
            language='en', 
            entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "US_SSN"]
        )
        redacted = anonymizer_engine.anonymize(text=text_data, analyzer_results=results).text
        if not redacted:
            raise ValueError("Redaction engine returned empty string.")
        return redacted
    except Exception as e:
        logger.critical(f"PHI Redaction failure: {e}. Aborting pipeline to prevent leakage.")
        raise

# ── Manifest Logic ──────────────────────────────────────────────────────────
def load_manifest(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        logger.warning(f"Manifest not found at {path}.")
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return ClinicalManifest(**data).model_dump(by_alias=True)
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Manifest corruption: {e}")
        raise

def get_system_instruction() -> str:
    """Loads versioned system prompt for clinical auditability."""
    try:
        with open(settings.system_prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load system prompt: {e}. Falling back to default.")
        return "You are a clinical decision support assistant. Analyze PSA trends and lab results."

# ── Async Gemini Execution ──────────────────────────────────────────────────
async def run_gemini_async(manifest_data: Dict[str, Any]) -> ClinicalAssessment:
    """
    Executes the full pipeline (Redaction + LLM) in a thread pool.
    Clinical Note: AI outputs are probabilistic; always verify against clinical guidelines.
    """
    client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
    system_instruction = get_system_instruction()

    def _execute_pipeline():
        # Redaction failure will raise exception here, stopping the pipeline
        redacted_json = redact_phi_sync(manifest_data)
        prompt = f"Analyze the following patient data: {redacted_json}"
        
        return client.models.generate_content(
            model=settings.model_name,
            contents=prompt,
            config=gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ClinicalAssessment,
                system_instruction=system_instruction,
                temperature=0.1,
            )
        )

    try:
        loop = asyncio.get_running_loop()
        resp = await loop.run_in_executor(executor, _execute_pipeline)
        
        assessment = ClinicalAssessment.model_validate_json(resp.text)
        
        logger.info(f"Clinical decision generated. Confidence: {assessment.confidence_score}")
        return assessment
    except Exception as e:
        logger.error(f"Pipeline execution failure: {e}")
        raise

async def main():
    try:
        manifest = load_manifest(settings.manifest_path)
        if not manifest:
            return
        
        report = await run_gemini_async(manifest)
        print(report.model_dump_json(indent=2))
    except Exception as e:
        logger.critical(f"Pipeline failure: {e}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        executor.shutdown(wait=True)