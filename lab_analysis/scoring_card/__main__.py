"""lab_analysis.scoring_card.__main__ — 支持 `python -m lab_analysis.scoring_card`。

P0-2: 原 scoring_card.py 拆包为子目录时遗漏了 __main__.py.
"""
from . import main

if __name__ == "__main__":
    main()
