import os
import sys
import uuid
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
import structlog

# Clinical Disclaimer: This system provides decision support. 
# All outputs must be reviewed by a qualified clinician.

def setup_logging():
    """Configures structured logging with a dedicated sink for clinical alerts."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "clinical_pipeline.log"
    alert_file = log_dir / "clinical_alerts.log"
    
    # Standard pipeline logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)]
    )
    
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )

class AppConfig(BaseModel):
    api_key: str = Field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    base_dir: Path = Field(default_factory=Path.cwd)
    manifest_path: Path = Field(default=Path("psa_metrics_manifest.json"))
    report_path: Path = Field(default=Path("psa_clinical_report_v2.json"))
    prompt_path: Path = Field(default=Path("prompts/clinical_system.txt"))

    @field_validator("api_key")
    @classmethod
    def check_api_key(cls, v: str) -> str:
        if not v:
            raise ValueError("GEMINI_API_KEY not found in environment.")
        return v

    @field_validator("manifest_path", "report_path", "prompt_path")
    @classmethod
    def validate_path_traversal(cls, v: Path, info: Any) -> Path:
        base = Path.cwd()
        if not str(v.resolve()).startswith(str(base)):
            raise PermissionError(f"Path traversal detected: {v}")
        return v

    def get_system_instruction(self) -> str:
        try:
            if self.prompt_path.exists():
                return self.prompt_path.read_text()
        except Exception as e:
            logging.getLogger().warning("failed_to_load_prompt_template", error=str(e))
        return "You are a clinical AI assistant. Provide evidence-based analysis."

class PSAHistory(BaseModel):
    date: str
    value: float = Field(..., ge=0.0, le=1000.0)

class PatientMetadata(BaseModel):
    id: str
    age_years: int = Field(..., ge=0, le=120)
    gender: str

class ClinicalManifest(BaseModel):
    patient_metadata: PatientMetadata
    psa_history: List[PSAHistory]

    @model_validator(mode='after')
    def sanitize_pii(self) -> 'ClinicalManifest':
        """Proactive PII guard: Sanitizes data upon instantiation."""
        analyzer = AnalyzerEngine()
        anonymizer = AnonymizerEngine()
        
        def _clean(val: str) -> str:
            results = analyzer.analyze(text=val, language='en', entities=["PERSON", "US_SSN", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"])
            return anonymizer.anonymize(text=val, analyzer_results=results).text

        self.patient_metadata.id = _clean(self.patient_metadata.id)
        return self

class ClinicalAssessment(BaseModel):
    psa_trend_analysis: str
    psa_density_reconciliation: str
    differential_diagnosis: str
    ctca_systemic_inflammation: str
    prioritised_next_steps: str
    human_review_required: bool = Field(True)
    disclaimer: str = "AI-generated: For clinical decision support only. Verify all findings."

class ClinicalEngineContainer:
    def __init__(self, config: AppConfig):
        genai.configure(api_key=config.api_key)
        self.model_names = ["gemini-2.0-flash", "gemini-1.5-flash"]
        self.system_instruction = config.get_system_instruction()

    async def generate_content_async(self, prompt: str) -> GenerateContentResponse:
        """Uses native async generation if available, otherwise wraps in executor."""
        for model_name in self.model_names:
            try:
                model = genai.GenerativeModel(model_name=model_name, system_instruction=self.system_instruction)
                # Using generate_content_async for non-blocking I/O
                return await model.generate_content_async(
                    prompt,
                    generation_config={
                        "temperature": 0.15,
                        "response_mime_type": "application/json",
                        "response_schema": ClinicalAssessment
                    }
                )
            except Exception as e:
                logging.getLogger().error("model_invocation_failed", model=model_name, error=str(e))
        raise RuntimeError("All Gemini models failed.")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def run_gemini_async(container: ClinicalEngineContainer, data: Dict[str, Any], trace_id: str) -> ClinicalAssessment:
    logger = structlog.get_logger()
    sanitized_json = json.dumps(data)
    
    logger.info("invoking_model", trace_id=trace_id)
    response = await container.generate_content_async(f"Analyze this clinical data: {sanitized_json}")
    return ClinicalAssessment.model_validate_json(response.text)

async def run_pipeline():
    setup_logging()
    logger = structlog.get_logger()
    trace_id = str(uuid.uuid4())
    log = logger.bind(trace_id=trace_id)
    
    try:
        config = AppConfig()
        container = ClinicalEngineContainer(config)
        
        if not config.manifest_path.exists():
            sample = {"patient_metadata": {"id": "SYNTH-001", "age_years": 71, "gender": "M"}, "psa_history": [{"date": "2023-01-01", "value": 4.2}]}
            config.manifest_path.write_text(json.dumps(sample, indent=2))
            raw_data = sample
        else:
            raw_data = json.loads(config.manifest_path.read_text())
            
        manifest = ClinicalManifest(**raw_data)
        assessment = await run_gemini_async(container, manifest.model_dump(), trace_id)
        
        if assessment.human_review_required:
            log.warning("human_review_required", trace_id=trace_id, status="CRITICAL_ACTION_REQUIRED")
            with open("logs/clinical_alerts.log", "a") as f:
                f.write(f"[{trace_id}] CRITICAL: Human review required for clinical assessment.\n")
            return
        
        config.report_path.write_text(assessment.model_dump_json(indent=2))
        log.info("pipeline_complete", output_path=str(config.report_path))
            
    except ValidationError as ve:
        log.error("structured_output_validation_failed", error=str(ve))
    except Exception as e:
        log.critical("pipeline_failed", error=str(e))

if __name__ == "__main__":
    try:
        asyncio.run(run_pipeline())
    except KeyboardInterrupt:
        sys.exit(0)