"""Read DSPy compile cache hit/miss metrics.

Usage:
    python scripts/dspy_cache_stats.py            # pretty table
    python scripts/dspy_cache_stats.py --reset    # clear metrics
    python scripts/dspy_cache_stats.py --json     # raw JSON to stdout
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lab_analysis.dspy_modules._cache_metrics import get_stats, reset  # noqa: E402


def _fmt(n: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{n}/{total} ({n * 100 // total}%)"


def _print_table(stats: dict) -> None:
    print("DSPy compile cache hit-rate")
    print("=" * 60)
    modules = stats.get("modules", {})
    if not modules:
        print("  (no metrics recorded yet — run a pipeline first)")
        return
    print(f"{'module':<32} {'hit':<14} {'miss':<14} {'load_fail':<14}")
    print("-" * 76)
    for name in sorted(modules):
        m = modules[name]
        total = m["hit"] + m["miss"] + m["load_fail"]
        print(
            f"{name:<32} "
            f"{_fmt(m['hit'], total):<14} "
            f"{_fmt(m['miss'], total):<14} "
            f"{_fmt(m['load_fail'], total):<14}"
        )
    t = stats["totals"]
    total_all = t["hit"] + t["miss"] + t["load_fail"]
    print("-" * 76)
    print(
        f"{'TOTAL':<32} "
        f"{_fmt(t['hit'], total_all):<14} "
        f"{_fmt(t['miss'], total_all):<14} "
        f"{_fmt(t['load_fail'], total_all):<14}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="clear metrics and exit")
    parser.add_argument("--json", action="store_true", help="print raw JSON to stdout")
    args = parser.parse_args()

    if args.reset:
        reset()
        print("metrics reset.")
        return 0

    stats = get_stats()
    if args.json:
        sys.stdout.write(json.dumps(stats, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    else:
        _print_table(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
