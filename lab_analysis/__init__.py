"""
Lab-Analysis: 慢性胰腺炎检验数据自动化分析 Pipeline（检验 + 文献 + 影像 + 综合报告）。
"""

# 自动加载 .env 文件中的环境变量
try:
    from dotenv import load_dotenv
    from pathlib import Path
    # 查找项目根目录（包含 .env 文件的目录）
    project_root = Path(__file__).resolve().parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file)
except ImportError:
    # 如果 python-dotenv 未安装，跳过加载
    pass

__version__ = "0.1.0"
