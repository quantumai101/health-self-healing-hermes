"""
tests/test_medical_kb.py
Tests for clinical classification functions.
"""

import sys
from unittest.mock import MagicMock
sys.modules['streamlit'] = MagicMock()

from data.medical_kb import classify_bmi, classify_bp, classify_glucose, classify_hba1c, classify_risk


class TestBMIClassification:
    def test_underweight(self):
        result = classify_bmi(16.0)
        assert result["band"] == "Underweight"
        assert result["status"] == "CRITICAL"

    def test_normal(self):
        result = classify_bmi(22.0)
        assert result["band"] == "Normal"
        assert result["status"] == "OK"

    def test_overweight(self):
        result = classify_bmi(27.0)
        assert result["band"] == "Overweight"
        assert result["status"] == "REVIEW"

    def test_obese_iii(self):
        result = classify_bmi(45.0)
        assert result["band"] == "Obese III"
        assert result["status"] == "CRITICAL"

    def test_risk_score_bounded(self):
        result = classify_bmi(22.0)
        assert 0.05 <= result["risk_score"] <= 0.98


class TestBPClassification:
    def test_normal(self):    assert classify_bp(110) == "Normal"
    def test_elevated(self):  assert classify_bp(125) == "Elevated"
    def test_stage1(self):    assert classify_bp(135) == "Stage 1 HTN"
    def test_stage2(self):    assert classify_bp(155) == "Stage 2 HTN"
    def test_crisis(self):    assert classify_bp(185) == "HTN Crisis"


class TestGlucoseClassification:
    def test_normal(self):      assert classify_glucose(4.5) == "Normal"
    def test_prediabetic(self): assert classify_glucose(6.0) == "Pre-diabetic"
    def test_diabetic(self):    assert classify_glucose(7.5) == "Diabetic"


class TestHbA1cClassification:
    def test_normal(self):      assert classify_hba1c(5.0) == "Normal"
    def test_prediabetic(self): assert classify_hba1c(6.0) == "Pre-diabetic"
    def test_diabetic(self):    assert classify_hba1c(7.0) == "Diabetic"


class TestRiskClassification:
    def test_low(self):      assert classify_risk(0.2) == "Low"
    def test_moderate(self): assert classify_risk(0.5) == "Moderate"
    def test_high(self):     assert classify_risk(0.7) == "High"
    def test_critical(self): assert classify_risk(0.9) == "Critical"
