"""
DSPy 模块包

包含基于 DSPy 框架优化的 LLM 模块
"""

from .literature_interpreter import LiteratureInterpreterModule, compile_interpreter, run_dspy_interpretation
from .final_report_generator import FinalReportGenerator, compile_report_generator, run_dspy_final_report
from .lab_data_extractor import LabDataExtractor, compile_lab_extractor, run_dspy_extraction
from .mri_analyzer import MRIAnalysisModule, compile_mri_analyzer, run_dspy_mri_analysis

__all__ = [
    'LiteratureInterpreterModule',
    'compile_interpreter',
    'run_dspy_interpretation',
    'FinalReportGenerator',
    'compile_report_generator',
    'run_dspy_final_report',
    'LabDataExtractor',
    'compile_lab_extractor',
    'run_dspy_extraction',
    'MRIAnalysisModule',
    'compile_mri_analyzer',
    'run_dspy_mri_analysis'
]
