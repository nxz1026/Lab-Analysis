"""tests.test_fhir_exporter — FHIR R4 Bundle 输出测试"""

import json

from lab_analysis.fhir_exporter import (
    _build_diagnostic_report,
    _build_inflammation_observation,
    _build_observation,
    _build_patient,
    _build_risk_assessment,
    build_fhir_bundle,
)


class TestBuildPatient:
    def test_has_required_fields(self):
        p = _build_patient("test_deid")
        assert p["resourceType"] == "Patient"
        assert p["id"] == "test_deid"
        assert p["identifier"][0]["value"] == "test_deid"


class TestBuildObservation:
    def test_normal_obs(self):
        obs = _build_observation("obs-1", "WBC", 6.5, "10^9/L", 3.5, 9.5)
        assert obs["resourceType"] == "Observation"
        assert obs["valueQuantity"]["value"] == 6.5
        assert "referenceRange" in obs
        assert "interpretation" not in obs  # within range

    def test_high_obs_has_interpretation(self):
        obs = _build_observation("obs-2", "hs-CRP", 12.3, "mg/L", 0, 1.0)
        assert obs["interpretation"][0]["coding"][0]["code"] == "H"

    def test_low_obs_has_interpretation(self):
        obs = _build_observation("obs-3", "WBC", 2.0, "10^9/L", 3.5, 9.5)
        assert obs["interpretation"][0]["coding"][0]["code"] == "L"

    def test_no_ref_range_no_crash(self):
        obs = _build_observation("obs-4", "TEST", 5.0, "U", None, None)
        assert "referenceRange" not in obs


class TestBuildInflammationObservation:
    def test_acute_status(self):
        obs = _build_inflammation_observation("deid", ["缓解期", "急性期"], ["2026-03-01", "2026-04-01"])
        assert obs is not None
        assert obs["valueCodeableConcept"]["coding"][0]["code"] == "acute"
        assert obs["effectiveDateTime"] == "2026-04-01"

    def test_empty_labels_returns_none(self):
        obs = _build_inflammation_observation("deid", [], [])
        assert obs is None


class TestBuildRiskAssessment:
    def test_includes_hypotheses(self):
        scoring = {
            "top_hypotheses": [
                {"hypothesis": "慢性胰腺炎", "confidence": 0.8},
                {"hypothesis": "急性感染", "confidence": 0.3},
            ],
            "dimension_scores": {"inflammation": 80, "lab_abnormality": 50},
        }
        ra = _build_risk_assessment("deid", scoring)
        assert ra["resourceType"] == "RiskAssessment"
        assert len(ra["prediction"]) == 2
        assert "note" in ra


class TestBuildDiagnosticReport:
    def test_includes_conclusion(self):
        scoring = {"top_hypotheses": [{"hypothesis": "慢性胰腺炎（活动期）", "confidence": 0.82}]}
        dr = _build_diagnostic_report("deid", ["obs-1"], scoring, "")
        assert dr["conclusion"] == "慢性胰腺炎（活动期）（置信度 82%）"


class TestBuildFhirBundle:
    def test_is_valid_bundle(self):
        bundle = build_fhir_bundle(
            deid="test",
            analysis_results={
                "inflammation_classification": {
                    "labels": ["急性期"], "report_dates": ["2026-04-01"],
                },
                "abnormal_summary": {},
            },
            scoring_card={"top_hypotheses": [], "dimension_scores": {}},
            alerts=[],
            report_md="# Test Report",
            lab_metrics=[{"metric": "WBC", "value": 6.5, "unit": "10^9/L", "date": "2026-04-01"}],
        )
        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"
        assert len(bundle["entry"]) >= 3

    def test_serializable(self):
        bundle = build_fhir_bundle(
            deid="test",
            analysis_results={
                "inflammation_classification": {"labels": [], "report_dates": []},
                "abnormal_summary": {},
            },
            scoring_card={"top_hypotheses": [], "dimension_scores": {}},
            alerts=[{"level": "CRITICAL", "message": "test alert"}],
            report_md="",
            lab_metrics=[],
        )
        dumped = json.dumps(bundle, ensure_ascii=False)
        loaded = json.loads(dumped)
        assert loaded["resourceType"] == "Bundle"
