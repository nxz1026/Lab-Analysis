"""支持: python -m lab_analysis --patient-id <id>（需在仓库根目录或已 pip install -e .）。"""

from .pipeline import main

if __name__ == "__main__":
    main()
