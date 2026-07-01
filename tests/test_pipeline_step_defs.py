"""tests.test_pipeline_step_defs — Pipeline 步骤定义单测。"""

from __future__ import annotations

from lab_analysis.pipeline.step_defs import CORE_STEPS, StepDef


class TestStepDef:
    def test_default_fatal(self):
        s = StepDef(name="test", module="test_mod")
        assert s.fatal is True

    def test_explicit_fatal(self):
        s = StepDef(name="test", module="test_mod", fatal=False)
        assert s.fatal is False

    def test_attributes(self):
        s = StepDef(name="③ 数据加载", module="data_loader")
        assert s.name == "③ 数据加载"
        assert s.module == "data_loader"


class TestCoreSteps:
    def test_has_three_steps(self):
        assert len(CORE_STEPS) == 3

    def test_all_are_stepdef(self):
        for s in CORE_STEPS:
            assert isinstance(s, StepDef)

    def test_first_step(self):
        assert CORE_STEPS[0].name == "③ 数据加载"
        assert CORE_STEPS[0].module == "data_loader"

    def test_second_step(self):
        assert CORE_STEPS[1].name == "④ 数据分析"
        assert CORE_STEPS[1].module == "data_analyzer"

    def test_third_step(self):
        assert CORE_STEPS[2].name == "⑤ 文献检索"
        assert CORE_STEPS[2].module == "literature_searcher"

    def test_all_fatal_by_default(self):
        for s in CORE_STEPS:
            assert s.fatal is True
