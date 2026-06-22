"""审计 4 个 dspy compiled JSON 的时效性。

关键检查：
1. compile 时间 vs 源代码最新改动时间
2. JSON 内 prompt 模板是否含旧 OCR endpoint (qwen-vl-plus / zhipu)
3. JSON metadata 中的 model / dataset 哈希
4. 与 dspy_modules/ 源文件的最后修改时间对比
"""

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(r"e:\2026Workplace\Code\Lab-Analysis")
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
        # dspy 保存的元数据键不固定,几个常见 key 都试一下
        created_at = (
            meta.get("created_at") or meta.get("compile_time") or meta.get("timestamp") or "unknown"
        )

        # 检查 prompt 文本
        text_blob = json.dumps(data, ensure_ascii=False)
        old_hits = [s for s in OLD_ENDPOINTS if s in text_blob]
        new_hits = [s for s in NEW_ENDPOINTS if s in text_blob]

        # 是否源文件改动后未重新 compile
        stale = latest_src_mtime > mtime
        if stale:
            overall_needs_recompile = True

        flag = "STALE " if stale else "OK     "
        print(f"\n  [{flag}] {json_path.name}")
        print(f"    mtime:      {datetime.fromtimestamp(mtime):%Y-%m-%d %H:%M} ({age_h:.1f}h ago)")
        print(f"    metadata:   created_at={created_at!r}")
        print(f"    keys:       {sorted(data.keys())[:8]}...")
        print(f"    old refs:   {old_hits if old_hits else '(none)'}")
        print(f"    new refs:   {new_hits if new_hits else '(none)'}")
        # 显示 prompt signature
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


if __name__ == "__main__":
    main()
