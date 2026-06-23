"""lab_analysis.literature_searcher.__main__ — 支持 `python -m lab_analysis.literature_searcher`。

P0-2: 原 literature_searcher.py 拆包为子目录时遗漏了 __main__.py,
导致 pipeline 在 run_step 中以 `python -m lab_analysis.literature_searcher` 调用时
报 "is a package and cannot be directly executed". 这里从包内导入 main() 调用即可.
"""
from . import main

if __name__ == "__main__":
    main()
