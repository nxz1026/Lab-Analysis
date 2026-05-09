#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
便捷入口脚本 - 代理调用 lab_analysis.pipeline

用法（二选一，效果相同）：
  python run_analysis.py --patient-id <id>
  python -m lab_analysis --patient-id <id>

注意：此脚本仅为便捷入口，核心逻辑在 lab_analysis.pipeline 中实现。
      推荐直接使用 python -m lab_analysis 以保持统一。
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lab_analysis.pipeline import main

if __name__ == "__main__":
    main()
