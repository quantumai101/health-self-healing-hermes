"""
tests/test_agents.py
Phase 3 tests — verify all agent offline fallbacks return non-empty strings.
Run with: pytest tests/test_agents.py -v
"""

import pytest
from unittest.mock import patch, MagicMock
import sys

# ---------------------------------------------------------------------------
# Mock streamlit with a proper dict-backed session_state BEFORE any imports
# ---------------------------------------------------------------------------
_session_store = {}

mock_session_state = MagicMock()
mock_session_state.__contains__ = lambda self, key: key in _session_store
mock_session_state.__getitem__  = lambda self, key: _session_store[key]
mock_session_state.__setitem__  = lambda self, key, val: _session_store.__setitem__(key, val)
mock_session_state.get          = lambda key, default=None: _session_store.get(key, default)

mock_st = MagicMock()
mock_st.session_state = mock_session_state
sys.modules['streamlit'] = mock_st

# Now safe to import agents
from agents.nova       import NovaAgent
from agents.axiom      import AxiomAgent
from agents.nexus      import NexusAgent
from agents.prometheus import PrometheusAgent
from agents.sentinel   import SentinelAgent


def _mock_gemini_fail(*args, **kwargs):
    """Simulate Gemini total failure — returns offline_fallback."""
    return kwargs.get("offline_fallback", "offline")


@pytest.fixture(autouse=True)
def patch_gemini():
    """Patch gemini_chat to always return offline fallback for unit tests."""
    with patch("agents.nova.gemini_chat",       side_effect=_mock_gemini_fail), \
         patch("agents.axiom.gemini_chat",      side_effect=_mock_gemini_fail), \
         patch("agents.nexus.gemini_chat",      side_effect=_mock_gemini_fail), \
         patch("agents.prometheus.gemini_chat", side_effect=_mock_gemini_fail), \
         patch("agents.sentinel.gemini_chat",   side_effect=_mock_gemini_fail):
        yield


class TestNovaAgent:
    def setup_method(self):
        self.agent = NovaAgent()

    def test_ingest_command_returns_non_empty(self):
        result = self.agent.run("Ingest synthetic patient biometric data and run clinical quality checks")
        assert isinstance(result, str) and len(result) > 10

    def test_ehr_command_returns_non_empty(self):
        result = self.agent.run("Summarize this EHR document")
        assert isinstance(result, str) and len(result) > 10

    def test_default_command_returns_non_empty(self):
        result = self.agent.run("unknown nova command")
        assert isinstance(result, str) and len(result) > 10

    def test_summarize_ehr_text(self):
        result = self.agent.summarize_ehr_text("Patient has hypertension and diabetes.")
        assert isinstance(result, str) and len(result) > 10


class TestAxiomAgent:
    def setup_method(self):
        self.agent = AxiomAgent()

    def test_train_command_returns_non_empty(self):
        result = self.agent.run("Train the XGBoost chronic disease risk model and show AUC score")
        assert isinstance(result, str) and len(result) > 10

    def test_predict_command_returns_non_empty(self):
        result = self.agent.run("Predict chronic disease risk for a patient with BMI 38.5")
        assert isinstance(result, str) and len(result) > 10

    def test_imaging_command_returns_non_empty(self):
        result = self.agent.run("Analyse medical imaging scan results")
        assert isinstance(result, str) and len(result) > 10

    def test_predict_patient_risk(self):
        result = self.agent.predict_patient_risk(bmi=35.0, systolic=145, glucose=6.8, age=55)
        assert isinstance(result, str) and len(result) > 10

    def test_analyze_imaging(self):
        result = self.agent.analyze_imaging("bilateral consolidation", "Chest X-Ray")
        assert isinstance(result, str) and len(result) > 10


class TestNexusAgent:
    def setup_method(self):
        self.agent = NexusAgent()

    def test_simulation_command_returns_non_empty(self):
        result = self.agent.run("Run population health digital twin simulation on default cohort")
        assert isinstance(result, str) and len(result) > 10


class TestPrometheusAgent:
    def setup_method(self):
        self.agent = PrometheusAgent()

    def test_report_command_returns_non_empty(self):
        result = self.agent.run("Generate an executive weekly population health report")
        assert isinstance(result, str) and len(result) > 10

    def test_news_command_returns_non_empty(self):
        result = self.agent.run("Show latest health news")
        assert isinstance(result, str) and len(result) > 10

    def test_get_health_news(self):
        result = self.agent.get_health_news()
        assert isinstance(result, str) and len(result) > 10

    def test_analyze_sentiment(self):
        result = self.agent.analyze_sentiment("Patient presents with worsening chest pain.")
        assert isinstance(result, str) and len(result) > 10


class TestSentinelAgent:
    def setup_method(self):
        self.agent = SentinelAgent()

    def test_compliance_command_returns_non_empty(self):
        result = self.agent.run("Run health data compliance scan and rotate the API secret")
        assert isinstance(result, str) and len(result) > 10

    def test_generate_compliance_report(self):
        result = self.agent.generate_compliance_report()
        assert isinstance(result, str) and len(result) > 10
