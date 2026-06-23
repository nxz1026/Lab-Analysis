"""Scan for hard-coded API keys in source code.

Patterns:
    - sk- / sk_live_ / sk_test_   (OpenAI/DeepSeek/Stripe)
    - AIzaSy...                   (Google)
    - ghp_ / gho_ / ghu_ / ghs_   (GitHub)
    - xox[bpoas]-...              (Slack)
    - AKIA[0-9A-Z]{16}            (AWS access key)
    - api_key = "..." / api-key: "..." / apikey = "..."

Excludes:
    - tests/, docs/, .env, .env.example
    - this very file (self-exclusion)

Usage:
    python scripts/scan_hardcoded_keys.py           # print findings + exit 0/1
    python scripts/scan_hardcoded_keys.py --quiet   # only exit code
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELF = Path(__file__).resolve()

# Heuristics for suspicious keys. False positives reviewed manually.
PATTERNS = [
    ("openai/sk", re.compile(r"\bsk-[A-Za-z0-9]{16,}\b")),
    ("openai/proj", re.compile(r"\bsk_proj-[A-Za-z0-9_-]{16,}\b")),
    ("github/token", re.compile(r"\b(ghp|gho|ghu|ghs)_[A-Za-z0-9]{16,}\b")),
    ("google", re.compile(r"\bAIzaSy[A-Za-z0-9_-]{16,}\b")),
    ("slack", re.compile(r"\bxox[bpoas]-[A-Za-z0-9-]{10,}\b")),
    ("aws_access", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("stripe", re.compile(r"\bsk_(live|test)_[A-Za-z0-9]{16,}\b")),
    # generic: api_key = "literal" / api-key: 'literal' / apikey="..."
    (
        "generic_assign",
        re.compile(
            r"""\b(api[_-]?key|apikey|access[_-]?token|secret[_-]?key)\s*[:=]\s*["']([^"'\s]{16,})["']""",
            re.IGNORECASE,
        ),
    ),
]

# Names whose value is allowed to be a *placeholder* (not a real key).
PLACEHOLDER_RE = re.compile(
    r"^(your[_-]?|<.*>|\$\{|placeholder|example|dummy|fake|xxx+|test.*)$",
    re.IGNORECASE,
)


def _is_placeholder(value: str) -> bool:
    return bool(PLACEHOLDER_RE.match(value.strip()))


def scan(target: Path, exclude_dirs: set[str]) -> list[tuple[str, int, str, str]]:
    findings: list[tuple[str, int, str, str]] = []
    for path in target.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(part in exclude_dirs for part in rel.parts):
            continue
        if path.resolve() == SELF:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            # strip inline comments to reduce noise
            stripped = line.split("#", 1)[0]
            for kind, pat in PATTERNS:
                m = pat.search(stripped)
                if not m:
                    continue
                # if generic_assign, check value against placeholder list
                if kind == "generic_assign":
                    value = m.group(2)
                    if _is_placeholder(value):
                        continue
                findings.append((str(rel), lineno, kind, stripped.strip()[:120]))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true", help="only return exit code, no output")
    args = parser.parse_args()

    targets = [ROOT / "lab_analysis", ROOT / "mcp_server.py"]
    exclude = {"tests", "docs", ".venv", "venv", "__pycache__"}
    all_hits: list[tuple[str, int, str, str]] = []
    for t in targets:
        if t.exists():
            all_hits.extend(scan(t, exclude))

    if all_hits:
        if not args.quiet:
            print(f"[FAIL] 发现 {len(all_hits)} 处疑似硬编码 API Key:\n")
            for path, lineno, kind, snippet in all_hits:
                print(f"  {path}:{lineno}  [{kind}]  {snippet}")
            print("\n请改为从环境变量 / .env 读取，禁止提交明文 Key。")
        return 1
    if not args.quiet:
        print("[OK] 未发现硬编码 API Key。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
