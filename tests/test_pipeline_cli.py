"""tests/test_pipeline_cli.py — pipeline/cli.py 测试

覆盖 repo_root() / _load_patient_mapping() / get_deid() / parse_args()。
parse_args() 通过 sys.argv mock 走全部分支。
"""

import json
import sys

import pytest


@pytest.fixture
def work_root_with_hermes(tmp_path, monkeypatch):
    """临时 WORK_ROOT，含 .hermes/patient_mapping.json"""
    import lab_analysis.pipeline.cli as cli_mod
    import lab_analysis.utils as utils

    monkeypatch.setattr(utils, "WORK_ROOT", tmp_path)
    monkeypatch.setattr(cli_mod, "WORK_ROOT", tmp_path)

    hermes = tmp_path / ".hermes"
    hermes.mkdir()
    mapping_file = hermes / "patient_mapping.json"
    mapping = {"existing_deid_aaa": "510101199001011234"}
    mapping_file.write_text(json.dumps(mapping), encoding="utf-8")
    return tmp_path, mapping


class TestRepoRoot:
    def test_repo_root_is_repo_root(self):
        from lab_analysis.pipeline.cli import repo_root

        root = repo_root()
        assert (root / "pyproject.toml").exists()
        assert (root / "lab_analysis").is_dir()


class TestLoadPatientMapping:
    def test_no_file_returns_empty(self, tmp_path, monkeypatch):
        import lab_analysis.pipeline.cli as cli_mod

        monkeypatch.setattr(cli_mod, "WORK_ROOT", tmp_path)
        from lab_analysis.pipeline.cli import _load_patient_mapping

        assert _load_patient_mapping() == {}

    def test_invalid_json_returns_empty(self, tmp_path, monkeypatch):
        import lab_analysis.pipeline.cli as cli_mod

        monkeypatch.setattr(cli_mod, "WORK_ROOT", tmp_path)
        (tmp_path / ".hermes").mkdir()
        (tmp_path / ".hermes" / "patient_mapping.json").write_text(
            "not json", encoding="utf-8"
        )
        from lab_analysis.pipeline.cli import _load_patient_mapping

        assert _load_patient_mapping() == {}

    def test_non_dict_returns_empty(self, tmp_path, monkeypatch):
        import lab_analysis.pipeline.cli as cli_mod

        monkeypatch.setattr(cli_mod, "WORK_ROOT", tmp_path)
        (tmp_path / ".hermes").mkdir()
        (tmp_path / ".hermes" / "patient_mapping.json").write_text(
            '["list", "not", "dict"]', encoding="utf-8"
        )
        from lab_analysis.pipeline.cli import _load_patient_mapping

        assert _load_patient_mapping() == {}

    def test_dict_loaded_with_str_conversion(self, tmp_path, monkeypatch):
        import lab_analysis.pipeline.cli as cli_mod

        monkeypatch.setattr(cli_mod, "WORK_ROOT", tmp_path)
        (tmp_path / ".hermes").mkdir()
        (tmp_path / ".hermes" / "patient_mapping.json").write_text(
            json.dumps({123: 456}), encoding="utf-8"  # int keys/values
        )
        from lab_analysis.pipeline.cli import _load_patient_mapping

        result = _load_patient_mapping()
        assert result == {"123": "456"}


class TestGetDeid:
    def test_from_mapping_returns_existing_deid(self, work_root_with_hermes):
        from lab_analysis.pipeline.cli import get_deid

        result = get_deid("510101199001011234")
        assert result == "existing_deid_aaa"

    def test_no_mapping_calls_encode(self, work_root_with_hermes):
        from lab_analysis.patient_id import encode
        from lab_analysis.pipeline.cli import get_deid

        new_id = "110101199001011234"  # 不在 mapping 里
        expected = encode(new_id)
        assert get_deid(new_id) == expected

    def test_empty_mapping_always_encodes(self, tmp_path, monkeypatch):
        import lab_analysis.pipeline.cli as cli_mod
        import lab_analysis.utils as utils

        monkeypatch.setattr(utils, "WORK_ROOT", tmp_path)
        monkeypatch.setattr(cli_mod, "WORK_ROOT", tmp_path)
        from lab_analysis.patient_id import encode
        from lab_analysis.pipeline.cli import get_deid

        assert get_deid("X" * 18) == encode("X" * 18)


class TestParseArgs:
    @pytest.fixture(autouse=True)
    def _restore_argv(self):
        """确保每次测试后恢复 argv"""
        original = sys.argv[:]
        yield
        sys.argv[:] = original

    def _run_parse(self, argv):
        sys.argv[:] = ["pipeline"] + argv
        from lab_analysis.pipeline.cli import parse_args
        return parse_args()

    def test_defaults(self):
        args = self._run_parse([])
        assert args.skip_llm is False
        assert args.skip_imaging is False
        assert args.skip_ingest is False
        assert args.use_dspy is False
        assert args.lit_filter_scenario == "differential_diagnosis"
        assert args.lit_filter_top_k == 8
        assert args.keep_last == 3

    def test_all_skip_flags(self):
        args = self._run_parse([
            "--skip-llm", "--skip-imaging", "--skip-ingest",
            "--skip-lit-filter", "--skip-pdf", "--skip-fhir",
            "--skip-scoring", "--skip-cleanup",
            "--no-interactive", "--auto-queries",
        ])
        for f in ("skip_llm", "skip_imaging", "skip_ingest", "skip_lit_filter",
                  "skip_pdf", "skip_fhir", "skip_scoring", "skip_cleanup",
                  "no_interactive", "auto_queries"):
            assert getattr(args, f) is True

    def test_use_dspy_and_compare(self):
        args = self._run_parse(["--use-dspy", "--compare-report-modes"])
        assert args.use_dspy is True
        assert args.compare_report_modes is True

    def test_lit_filter_options(self):
        args = self._run_parse([
            "--lit-filter-scenario", "prognosis",
            "--lit-filter-top-k", "15",
        ])
        assert args.lit_filter_scenario == "prognosis"
        assert args.lit_filter_top_k == 15

    def test_lit_filter_scenario_choices(self):
        for s in ("early_diagnosis", "differential_diagnosis", "prognosis"):
            args = self._run_parse(["--lit-filter-scenario", s])
            assert args.lit_filter_scenario == s

    def test_report_type_choices(self):
        for t in ("outpatient", "inpatient"):
            args = self._run_parse(["--report-type", t])
            assert args.report_type == t

    def test_ingest_options(self):
        args = self._run_parse([
            "--ingest-lab", "a.jpg", "b.jpg",
            "--ingest-dicom-zip", "x.zip",
            "--ingest-dicom-dir", "y",
            "--ingest-mri-report", "r.txt",
            "--report-date", "2026-06-21",
        ])
        assert args.ingest_lab == ["a.jpg", "b.jpg"]
        assert args.ingest_dicom_zip == "x.zip"
        assert args.ingest_dicom_dir == "y"
        assert args.ingest_mri_report == "r.txt"
        assert args.report_date == "2026-06-21"

    def test_keep_last(self):
        args = self._run_parse(["--keep-last", "5"])
        assert args.keep_last == 5