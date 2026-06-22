"""
DSPy 模块包

包含基于 DSPy 框架优化的 LLM 模块
"""

from .final_report_generator import (
    FinalReportGenerator,
    compile_report_generator,
    run_dspy_final_report,
)
from .lab_data_extractor import LabDataExtractor, compile_lab_extractor, run_dspy_extraction
from .literature_interpreter import (
    LiteratureInterpreterModule,
    compile_interpreter,
    run_dspy_interpretation,
)
from .mri_analyzer import MRIAnalysisModule, compile_mri_analyzer, run_dspy_mri_analysis
from .prompt_inspector import (
    extract_module_prompts,
    get_actual_dspy_prompt,
    save_actual_dspy_prompt,
    save_prompts_to_json,
    save_prompts_to_markdown,
)

__all__ = [
    "LiteratureInterpreterModule",
    "compile_interpreter",
    "run_dspy_interpretation",
    "FinalReportGenerator",
    "compile_report_generator",
    "run_dspy_final_report",
    "LabDataExtractor",
    "compile_lab_extractor",
    "run_dspy_extraction",
    "MRIAnalysisModule",
    "compile_mri_analyzer",
    "run_dspy_mri_analysis",
    "extract_module_prompts",
    "save_prompts_to_json",
    "save_prompts_to_markdown",
    "get_actual_dspy_prompt",
    "save_actual_dspy_prompt",
]
