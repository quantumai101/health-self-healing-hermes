import os
import sys
import uuid
import json
import logging
import asyncio
import hmac
import hashlib
import aiofiles
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import TimedRotatingFileHandler
from typing import List, Dict, Any, Protocol, Optional
from pathlib import Path
from tenacity import retry, stop_after_attempt, wait_exponential
from pydantic import BaseModel, Field, ValidationError, field_validator
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
import google.generativeai as genai
from google.generativeai.types import GenerateContentResponse
import structlog

# Clinical Disclaimer: This system provides decision support. 
# All outputs must be reviewed by a qualified clinician.
# Uncertainty Disclaimer: AI models may hallucinate; verify all clinical data against source records.

class SecretManager(Protocol):
    def get_secret(self, key: str) -> str: ...

class EnvSecretManager:
    """Production implementation should replace this with AWS Secrets Manager or HashiCorp Vault."""
    def get_secret(self, key: str) -> str:
        val = os.environ.get(key)
        if not val:
            raise RuntimeError(f"Secret {key} not found in secure vault.")
        return val

class FileSystemProvider(Protocol):
    async def read_text(self, path: Path) -> str: ...
    async def write_text(self, path: Path, content: str) -> None: ...
    async def exists(self, path: Path) -> bool: ...

class AsyncLocalFileSystem:
    async def read_text(self, path: Path) -> str:
        async with aiofiles.open(path, mode='r') as f:
            return await f.read()
    async def write_text(self, path: Path, content: str) -> None:
        async with aiofiles.open(path, mode='w') as f:
            await f.write(content)
    async def exists(self, path: Path) -> bool:
        return path.exists()

def setup_logging():
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "secure_audit.log"
    handler = TimedRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=30)
    logging.basicConfig(level=logging.INFO, format="%(message)s", handlers=[handler])
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )

class AuditLogger:
    @staticmethod
    def log_decision(trace_id: str, event: str, details: Dict[str, Any], secrets: SecretManager):
        logger = structlog.get_logger("audit_sink")
        secret = secrets.get_secret("AUDIT_SECRET").encode()
        payload = f"{trace_id}:{event}:{json.dumps(details)}".encode()
        signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        logger.info("clinical_audit_event", trace_id=trace_id, event=event, signature=signature, **details)

class AppConfig(BaseModel):
    api_key: str = Field(default_factory=lambda: os.environ.get("GEMINI_API_KEY", ""))
    base_dir: Path = Field(default_factory=Path.cwd)
    manifest_path: Path = Field(default=Path("psa_metrics_manifest.json"))
    report_path: Path = Field(default=Path("psa_clinical_report_v2.json"))
    prompt_path: Path = Field(default=Path("prompts/clinical_system.txt"))

    @field_validator("api_key")
    @classmethod
    def check_api_key(cls, v: str) -> str:
        if not v: raise ValueError("GEMINI_API_KEY not found.")
        return v

    async def get_system_instruction(self, fs: FileSystemProvider) -> str:
        if await fs.exists(self.prompt_path):
            return await fs.read_text(self.prompt_path)
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

class PIIProcessor:
    def __init__(self):
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
        self.executor = ThreadPoolExecutor(max_workers=2)

    def _clean(self, val: str) -> str:
        if not isinstance(val, str): return val
        results = self.analyzer.analyze(text=val, language='en', entities=["PERSON", "US_SSN", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"])
        return self.anonymizer.anonymize(text=val, analyzer_results=results).text

    async def sanitize(self, manifest: ClinicalManifest) -> ClinicalManifest:
        loop = asyncio.get_running_loop()
        manifest.patient_metadata.id = await loop.run_in_executor(self.executor, self._clean, manifest.patient_metadata.id)
        for entry in manifest.psa_history:
            entry.date = await loop.run_in_executor(self.executor, self._clean, entry.date)
        return manifest

class ClinicalAssessment(BaseModel):
    psa_trend_analysis: str
    psa_density_reconciliation: str
    differential_diagnosis: str
    ctca_systemic_inflammation: str
    prioritised_next_steps: str
    human_review_required: bool = Field(True)
    disclaimer: str = "AI-generated: For clinical decision support only. Verify all findings."

class ClinicalEngineContainer:
    def __init__(self, api_key: str, system_instruction: str):
        genai.configure(api_key=api_key)
        self.model_names = ["gemini-2.0-flash", "gemini-1.5-flash"]
        self.system_instruction = system_instruction

    async def generate_content_async(self, prompt: str) -> GenerateContentResponse:
        for model_name in self.model_names:
            try:
                model = genai.GenerativeModel(model_name=model_name, system_instruction=self.system_instruction)
                return await model.generate_content_async(prompt, generation_config={"temperature": 0.15, "response_mime_type": "application/json", "response_schema": ClinicalAssessment})
            except Exception as e:
                logging.getLogger().error("model_invocation_failed", model=model_name, error=str(e))
        raise RuntimeError("All Gemini models failed.")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def run_gemini_async(container: ClinicalEngineContainer, data: Dict[str, Any], trace_id: str) -> ClinicalAssessment:
    sanitized_json = json.dumps(data)
    response = await container.generate_content_async(f"Analyze this clinical data: {sanitized_json}")
    return ClinicalAssessment.model_validate_json(response.text)

def human_in_the_loop_verify(assessment: ClinicalAssessment) -> bool:
    print(f"\n--- CLINICAL REVIEW REQUIRED ---")
    print(f"Diagnosis: {assessment.differential_diagnosis}")
    signature = input("Enter clinician signature (name) to approve report: ").strip()
    return len(signature) > 0

async def run_pipeline():
    setup_logging()
    logger = structlog.get_logger()
    trace_id = str(uuid.uuid4())
    log = logger.bind(trace_id=trace_id)
    fs = AsyncLocalFileSystem()
    secrets = EnvSecretManager()
    
    try:
        config = AppConfig()
        pii_processor = PIIProcessor()
        
        if not await fs.exists(config.manifest_path):
            sample = {"patient_metadata": {"id": "SYNTH-001", "age_years": 71, "gender": "M"}, "psa_history": [{"date": "2023-01-01", "value": 4.2}]}
            await fs.write_text(config.manifest_path, json.dumps(sample, indent=2))
            raw_data = sample
        else:
            raw_data = json.loads(await fs.read_text(config.manifest_path))
            
        manifest = ClinicalManifest(**raw_data)
        # Sanitize immediately after loading
        manifest = await pii_processor.sanitize(manifest)
        
        container = ClinicalEngineContainer(config.api_key, await config.get_system_instruction(fs))
        assessment = await run_gemini_async(container, manifest.model_dump(), trace_id)
        
        if not human_in_the_loop_verify(assessment):
            log.error("human_verification_failed", trace_id=trace_id)
            return

        await fs.write_text(config.report_path, assessment.model_dump_json(indent=2))
        AuditLogger.log_decision(trace_id, "REPORT_GENERATED", {"path": str(config.report_path)}, secrets)
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