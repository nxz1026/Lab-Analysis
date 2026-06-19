"""
Lab-Analysis: 慢性胰腺炎检验数据自动化分析 Pipeline（检验 + 文献 + 影像 + 综合报告）。
"""

# 自动加载 .env 文件中的环境变量
try:
    from pathlib import Path

    from dotenv import load_dotenv
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
except ImportError:
    pass

# 跨平台适配：修复 Windows 控制台编码（中文输出）
try:
    from lab_analysis.utils import fix_console_encoding
    fix_console_encoding()
except Exception:
    pass

__version__ = "0.1.0"
