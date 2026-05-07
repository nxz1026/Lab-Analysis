#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
仓库根目录便捷入口，等价于：python -m lab_analysis --patient-id <id>

请在克隆目录下执行；或先 pip install -e .
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
