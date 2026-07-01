"""
文献解读模块 — 结合统计分析结果 + PubMed 文献，给出循证医学综合解读
用法: python literature_interpreter.py [--analysis JSON] [--lit JSON] [--out JSON]
"""

import json
import os
from datetime import datetime
from pathlib import Path

from lab_analysis.llm_client import call_chat_with_retry

from . import _log
from .config import WORK_ROOT

logger = _log.get_logger(__name__)
_DEEPSEEK_SYSTEM_PROMPT = (
    "你是一位专业的医学检验科和重症医学科临床顾问，结合循证医学证据为患者的检验数据提供深入解读。"
)


def load_json(path: str, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
        return default if default is not None else {}


def build_prompt(analysis_path: str, lit_path: str) -> str:
    analysis = load_json(analysis_path, {})
    lit = load_json(lit_path, {})
    corr = analysis.get("correlation_matrix", {})
    analysis.get("linear_regression", {})
    abnormal = analysis.get("abnormal_summary", {})
    abnormal_items = []
    for metric, info in abnormal.items():
        if isinstance(info, dict) and info.get("n_abnormal", 0) > 0:
            dates = info.get("abnormal_dates", [])
            rr = info.get("ref_range", "?")
            abnormal_items.append(
                f"- {metric}: 异常{(dates[0] if dates else '')}, n={info['n_abnormal']}, 参考区间 {rr}"
            )
    abnormal_text = "\n".join(abnormal_items) if abnormal_items else "无"
    strong_corr = []
    for pair, val in corr.items():
        if isinstance(val, (int, float)) and abs(val) >= 0.9:
            strong_corr.append(f"- {pair}: r={val:.3f}")
    corr_text = "\n".join(strong_corr) if strong_corr else "无"
    lit_texts = []
    papers = lit.get("all_papers", [])[:8]
    for p in papers:
        abstract = p.get("abstract", "")[:400]
        lit_texts.append(f"PMID:{p['pmid']} | {p.get('title', '')[:100]}\n摘要: {abstract}")
    lit_abstracts = "\n\n---\n\n".join(lit_texts)
    prompt = f"你是一位医学检验科 + 重症医学科双背景的临床顾问，正在为一名慢性胰腺炎患者的检验数据进行循证医学解读。\n\n## 患者检验统计结果\n\n### 异常指标\n{abnormal_text}\n\n### 强相关性发现（|r| ≥ 0.9）\n{corr_text}\n\n### 文献证据\n以下是从 PubMed 检索到的相关文献摘要：\n\n{lit_abstracts}\n\n## 解读要求\n\n请结合上述统计发现和文献证据，给出：\n\n1. **CRP-WBC 分离的机制解释**：为什么 CRP 升高但 WBC/NEUT# 下降？这在文献中是否有对应机制？\n2. **RDW 升高的临床意义**：结合文献，RDW 持续升高提示什么？\n3. **MONO% 代偿的免疫学意义**：单核细胞升高在炎症中扮演什么角色？\n4. **下一步循证建议**：根据文献，哪些检查最能区分细菌 vs 病毒/免疫抑制状态？\n5. **预后判断**：结合 RDW 和炎症指标，患者的预后信号是什么？\n\n请用中文回答，引用文献 PMID，格式规范。"
    return prompt


def call_deepseek(prompt: str) -> str:
    """调用 DeepSeek 进行文献循证解读（带指数退避重试）。

    已迁移至统一的 llm_client.call_chat_with_retry；此函数保留为薄封装，
    维持向后兼容的对外签名。
    """
    try:
        return call_chat_with_retry(
            "deepseek",
            user_prompt=prompt,
            system_prompt=_DEEPSEEK_SYSTEM_PROMPT,
            max_attempts=3,
            min_wait=2.0,
            max_wait=30.0,
        )
    except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError) as e:
        return f"错误：DeepSeek 调用失败 - {e}"


def main():
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="文献解读")
    parser.add_argument("--analysis", default=None, help="analysis_results.json 路径")
    parser.add_argument("--lit", default=None, help="literature_results.json 路径")
    parser.add_argument("--out", default=None, help="输出 JSON 路径")
    parser.add_argument("--id-card", default=None, help="脱敏ID(由 pipeline 传入)")
    args = parser.parse_args()

    wiki_data = WORK_ROOT / "data"
    if args.id_card:
        raw_ts = os.environ.get("ANALYSIS_TS", "")
        ts = raw_ts.split("/")[-1] if "/" in raw_ts else raw_ts or args.id_card
        lit_dir = wiki_data / args.id_card / ts / "03_literature"
        args.analysis = args.analysis or str(
            lit_dir.parent / "02_analyzed" / "analysis_results.json"
        )
        args.lit = args.lit or str(lit_dir / "literature_results.json")
        args.out = args.out or str(lit_dir / "literature_interpretation.json")
    else:
        args.analysis = args.analysis or str(wiki_data / "analysis_results.json")
        args.lit = args.lit or str(wiki_data / "literature_results.json")
        args.out = args.out or str(wiki_data / "literature_interpretation.json")
    for label, path in [("analysis_results", args.analysis), ("literature_results", args.lit)]:
        if path and (not Path(path).exists()):
            logger.info(f"[错误] 前置文件不存在: [{label}] {path}")
            raise SystemExit(1)
    logger.info("构建 prompt...")
    prompt = build_prompt(args.analysis, args.lit)
    logger.info("调用 DeepSeek...")
    response = call_deepseek(prompt)
    output = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": "deepseek-chat",
        "prompt_preview": prompt[:500] + "...",
        "response": response,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    md_path = Path(args.out).with_suffix(".md")
    md_content = f"# 循证医学解读报告\n\n**生成时间**: {output['generated']}\n**模型**: {output['model']}\n\n---\n\n{response}\n"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"\n[成功] 文献解读完成 → {args.out}")
    logger.info(f"[报告] Markdown 已保存: {md_path}")


if __name__ == "__main__":
    main()
