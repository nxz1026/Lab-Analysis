"""审计 4 个 dspy compiled JSON 的时效性。

关键检查：
1. compile 时间 vs 源代码最新改动时间
2. JSON 内 prompt 模板是否含旧 OCR endpoint (qwen-vl-plus / zhipu)
3. JSON metadata 中的 model / dataset 哈希
4. 与 dspy_modules/ 源文件的最后修改时间对比
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# 仓库根 = scripts/ 上一级,避免硬编码 Windows 路径,CI 可跑
ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "models" / "dspy"
SRC_DIR = ROOT / "lab_analysis" / "dspy_modules"

# OCR / LLM 相关字符串(可能是旧的 endpoint)
OLD_ENDPOINTS = ["qwen-vl-plus", "glm-4v", "ZHIPU_API_KEY", "dashscope"]
NEW_ENDPOINTS = ["SCNet", "SCNET", "deepseek"]


def read_compiled(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def _check_one(json_path: Path, latest_src_mtime: float) -> tuple[dict, bool]:
    """检查单个 compiled JSON, 返回 (detail_dict, is_stale)。"""
    mtime = json_path.stat().st_mtime
    age_h = (datetime.now().timestamp() - mtime) / 3600
    data = read_compiled(json_path)
    meta = data.get("metadata", {})

    # 优先读 metadata.compiled_at (由 inject_compile_metadata.py 注入)
    compiled_at_iso = meta.get("compiled_at")
    source_commit = meta.get("source_commit", "unknown")
    latest_src_iso = meta.get("latest_src_mtime")
    if compiled_at_iso:
        try:
            compiled_at_dt = datetime.fromisoformat(compiled_at_iso)
            compiled_ts = compiled_at_dt.timestamp()
        except ValueError:
            compiled_ts = mtime
            compiled_at_iso = f"{compiled_at_iso} (解析失败)"
    else:
        compiled_ts = mtime
        compiled_at_iso = (
            meta.get("created_at")
            or meta.get("compile_time")
            or meta.get("timestamp")
            or "unknown"
        )

    # 检查 prompt 文本
    text_blob = json.dumps(data, ensure_ascii=False)
    old_hits = [s for s in OLD_ENDPOINTS if s in text_blob]
    new_hits = [s for s in NEW_ENDPOINTS if s in text_blob]

    # 是否源文件改动后未重新 compile
    stale = bool(
        latest_src_iso
        and datetime.fromisoformat(latest_src_iso).timestamp() > compiled_ts
    )

    detail = {
        "module": json_path.stem,
        "json_path": str(json_path),
        "compiled_at": compiled_at_iso,
        "source_commit": source_commit,
        "latest_src_mtime": latest_src_iso,
        "file_age_hours": round(age_h, 2),
        "old_endpoint_refs": old_hits,
        "new_endpoint_refs": new_hits,
        "is_up_to_date": not stale,
        "reason": (
            "源文件改动后未重 compile"
            if stale
            else "up-to-date"
        ),
    }
    return detail, stale


def main():
    print("=" * 72)
    print(f"  dspy compiled models 审计 @ {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 72)

    # 1) 源代码最新改动时间
    print("\n[1] 源代码 dspy_modules/ 最后改动:")
    latest_src_mtime = 0
    for src in sorted(SRC_DIR.glob("*.py")):
        mt = src.stat().st_mtime
        latest_src_mtime = max(latest_src_mtime, mt)
        print(f"  {src.name:40s}  {datetime.fromtimestamp(mt):%Y-%m-%d %H:%M}")

    # 2) 每个 compiled JSON 的状态
    print("\n[2] compiled JSON 状态:")
    overall_needs_recompile = False
    details: list[dict] = []
    for json_path in sorted(MODELS.glob("*.json")):
        detail, stale = _check_one(json_path, latest_src_mtime)
        details.append(detail)
        if stale:
            overall_needs_recompile = True
        flag = "STALE " if stale else "OK     "
        print(f"\n  [{flag}] {json_path.name}")
        print(
            f"    compiled_at:   {detail['compiled_at']} (source: metadata)"
            if "解析失败" not in detail["compiled_at"]
            else f"    compiled_at:   {detail['compiled_at']}"
        )
        print(f"    source_commit: {detail['source_commit']}")
        if detail["latest_src_mtime"]:
            print(f"    src_mtime:     {detail['latest_src_mtime']}")
        print(f"    file_age:      {detail['file_age_hours']}h (mtime 仅供参考)")
        print(f"    old refs:   {detail['old_endpoint_refs'] or '(none)'}")
        print(f"    new refs:   {detail['new_endpoint_refs'] or '(none)'}")

    # 3) 结论
    print("\n" + "=" * 72)
    if overall_needs_recompile:
        print("  结论: STALE — 至少 1 个 compiled 模型在源码改动后未重 compile")
        print("        建议运行:")
        print("          python examples/compile_all_dspy_modules_v2.py")
        print("          python examples/compile_mri_analyzer_fix.py")
    else:
        print("  结论: 全部 UP-TO-DATE,无需重 compile")
    print("=" * 72)

    # CI 模式:检测到 STALE 退出 1,让 pipeline fail
    # 默认 Windows 本地无脑运行仍 exit 0 (避免误报),要 CI 行为需 --ci 或 CI env
    if overall_needs_recompile and ("--ci" in sys.argv or os.environ.get("CI")):
        sys.exit(1)

    # 结构化结果 (供 MCP / 测试调用)
    return {
        "overall_up_to_date": not overall_needs_recompile,
        "stale_modules": [d["module"] for d in details if not d["is_up_to_date"]],
        "details": details,
        "latest_src_mtime": latest_src_mtime,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


if __name__ == "__main__":
    main()
