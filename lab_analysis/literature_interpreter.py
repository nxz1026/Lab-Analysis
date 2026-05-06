#!/usr/bin/env python3
"""
文献解读模块 — 结合统计分析结果 + PubMed 文献，给出循证医学综合解读
用法: python literature_interpreter.py [--analysis JSON] [--lit JSON] [--out JSON]
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

WIKI_ROOT = Path.home() / "wiki"

def load_json(path: str, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default or {}


def build_prompt(analysis_path: str, lit_path: str) -> str:
    analysis = load_json(analysis_path, {})
    lit = load_json(lit_path, {})

    # 提取关键统计发现
    corr = analysis.get("correlation_matrix", {})
    regression = analysis.get("linear_regression", {})
    abnormal = analysis.get("abnormal_summary", {})

    # 收集异常指标（按 metric 分组）
    abnormal_items = []
    for metric, info in abnormal.items():
        if isinstance(info, dict) and info.get("n_abnormal", 0) > 0:
            dates = info.get("abnormal_dates", [])
            rr = info.get("ref_range", "?")
            abnormal_items.append(f"- {metric}: 异常{dates[0] if dates else ''}, n={info['n_abnormal']}, 参考区间 {rr}")
    abnormal_text = "\n".join(abnormal_items) if abnormal_items else "无"

    # 收集相关性发现（|r| >= 0.9）
    strong_corr = []
    for pair, val in corr.items():
        if isinstance(val, (int, float)) and abs(val) >= 0.9:
            strong_corr.append(f"- {pair}: r={val:.3f}")
    corr_text = "\n".join(strong_corr) if strong_corr else "无"

    # Top 5 论文摘要（取每类最相关的一篇）
    lit_texts = []
    papers = lit.get("all_papers", [])[:8]
    for p in papers:
        abstract = p.get("abstract", "")[:400]
        lit_texts.append(
            f"PMID:{p['pmid']} | {p.get('title','')[:100]}\n"
            f"摘要: {abstract}"
        )
    lit_abstracts = "\n\n---\n\n".join(lit_texts)

    prompt = f"""你是一位医学检验科 + 重症医学科双背景的临床顾问，正在为一名慢性胰腺炎患者的检验数据进行循证医学解读。

## 患者检验统计结果

### 异常指标
{abnormal_text}

### 强相关性发现（|r| ≥ 0.9）
{corr_text}

### 文献证据
以下是从 PubMed 检索到的相关文献摘要：

{lit_abstracts}

## 解读要求

请结合上述统计发现和文献证据，给出：

1. **CRP-WBC 分离的机制解释**：为什么 CRP 升高但 WBC/NEUT# 下降？这在文献中是否有对应机制？
2. **RDW 升高的临床意义**：结合文献，RDW 持续升高提示什么？
3. **MONO% 代偿的免疫学意义**：单核细胞升高在炎症中扮演什么角色？
4. **下一步循证建议**：根据文献，哪些检查最能区分细菌 vs 病毒/免疫抑制状态？
5. **预后判断**：结合 RDW 和炎症指标，患者的预后信号是什么？

请用中文回答，引用文献 PMID，格式规范。"""
    return prompt


def call_deepseek(prompt: str) -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        env_path = Path.home() / ".hermes" / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("DEEPSEEK_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
    if not api_key:
        return "错误：未设置 DEEPSEEK_API_KEY"

    import requests
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是一位专业的医学检验科和重症医学科临床顾问，结合循证医学证据为患者的检验数据提供深入解读。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
    }
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Hermes-Lab-Analyzer/1.0",
        },
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()
    return result["choices"][0]["message"]["content"]


def main():
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser(description="文献解读")
    parser.add_argument("--analysis", default=None,
                        help="analysis_results.json 路径")
    parser.add_argument("--lit", default=None,
                        help="literature_results.json 路径")
    parser.add_argument("--out", default=None,
                        help="输出 JSON 路径")
    parser.add_argument("--patient-id", default=None, help="诊疗卡号，设置后自动推导路径")
    args = parser.parse_args()

    wiki_data = Path.home() / "wiki" / "data"
    if args.patient_id:
        import os
        raw_ts = os.environ.get("ANALYSIS_TS", ""); ts = raw_ts.split("/")[-1] if "/" in raw_ts else (raw_ts or args.patient_id); data_dir = WIKI_ROOT / "data" / args.patient_id / ts
        pdata = wiki_data / args.patient_id / ts
        args.analysis = args.analysis or str(pdata / "analysis_results.json")
        args.lit = args.lit or str(pdata / "literature_results.json")
        args.out = args.out or str(pdata / "literature_interpretation.json")
    else:
        args.analysis = args.analysis or str(wiki_data / "analysis_results.json")
        args.lit = args.lit or str(wiki_data / "literature_results.json")
        args.out = args.out or str(wiki_data / "literature_interpretation.json")

    # 前置检查
    import sys
    for label, path in [("analysis_results", args.analysis), ("literature_results", args.lit)]:
        if path and not os.path.exists(path):
            print(f"❌ 前置文件不存在: [{label}] {path}")
            sys.exit(1)

    print("构建 prompt...")
    prompt = build_prompt(args.analysis, args.lit)

    print("调用 DeepSeek...")
    response = call_deepseek(prompt)

    output = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "deepseek-chat",
        "prompt_preview": prompt[:500] + "...",
        "response": response,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 同时写人类可读的 Markdown 版本
    md_path = Path(args.out).with_suffix(".md")
    md_content = f"# 循证医学解读报告\n\n**生成时间**: {output['generated']}\n**模型**: {output['model']}\n\n---\n\n{response}\n"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\n✅ 文献解读完成 → {args.out}")
    print(f"📄 Markdown 已保存: {md_path}")
    print("\n" + "="*60)
    print(response)
    print("="*60)


if __name__ == "__main__":
    main()
