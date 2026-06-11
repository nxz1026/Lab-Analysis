"""
DSPy 模块包

包含基于 DSPy 框架优化的 LLM 模块
"""

from .literature_interpreter import LiteratureInterpreterModule, compile_interpreter, run_dspy_interpretation

__all__ = [
    'LiteratureInterpreterModule',
    'compile_interpreter',
    'run_dspy_interpretation'
]
