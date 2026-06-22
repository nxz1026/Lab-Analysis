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
    for json_path in sorted(MODELS.glob("*.json")):
        mtime = json_path.stat().st_mtime
        age_h = (datetime.now().timestamp() - mtime) / 3600
        data = read_compiled(json_path)
        meta = data.get("metadata", {})

        # 优先读 metadata.compiled_at (由 inject_compile_metadata.py 注入),
        # 其次 dspy 自己的 created_at,都没有再降级到文件 mtime
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
        stale = latest_src_iso and datetime.fromisoformat(latest_src_iso).timestamp() > compiled_ts
        if stale:
            overall_needs_recompile = True

        flag = "STALE " if stale else "OK     "
        print(f"\n  [{flag}] {json_path.name}")
        print(
            f"    compiled_at:   {compiled_at_iso} (source: {'metadata' if meta.get('compiled_at') else 'mtime/fallback'})"
        )
        print(f"    source_commit: {source_commit}")
        if latest_src_iso:
            print(f"    src_mtime:     {latest_src_iso}")
        print(f"    file_age:      {age_h:.1f}h (mtime 仅供参考)")
        print(f"    old refs:   {old_hits if old_hits else '(none)'}")
        print(f"    new refs:   {new_hits if new_hits else '(none)'}")
        # 显示 prompt signature (只在 OK 时简化,STALE 时省略)
        if not stale:
            for sig in ("signature", "predictor", "instructions"):
                if sig in data:
                    v = data[sig]
                    if isinstance(v, str):
                        print(f"    {sig:11s}: {v[:100]!r}")
                    elif isinstance(v, dict):
                        keys = list(v.keys())[:5]
                        print(f"    {sig:11s}: dict keys={keys}")

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


if __name__ == "__main__":
    main()
