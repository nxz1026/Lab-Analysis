"""
Lab-Analysis: 慢性胰腺炎检验数据自动化分析 Pipeline（检验 + 文献 + 影像 + 综合报告）。
"""

from ._exceptions import SAFE_EXCEPTIONS
from ._phi_filter import install_global_phi_redaction

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

# 全局 PHI 脱敏: 必须走 LogRecord factory, 挂在 root logger 的 filter 对子 logger 无效
# (详见 _phi_filter.install_global_phi_redaction 的说明)
install_global_phi_redaction()

__version__ = "0.1.0"
