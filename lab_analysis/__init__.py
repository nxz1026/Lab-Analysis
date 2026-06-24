"""
Lab-Analysis: 慢性胰腺炎检验数据自动化分析 Pipeline（检验 + 文献 + 影像 + 综合报告）。
"""

import logging

from ._exceptions import SAFE_EXCEPTIONS
from ._phi_filter import PHIFilter

try:
    from pathlib import Path

    from dotenv import load_dotenv

    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
except ImportError:
    pass
try:
    from lab_analysis.utils import fix_console_encoding

    fix_console_encoding()
except SAFE_EXCEPTIONS:
    pass

logging.getLogger().addFilter(PHIFilter())

__version__ = "0.1.0"
