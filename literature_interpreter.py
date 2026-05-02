#!/usr/bin/env python3
"""文献解读：分析结果 + PubMed 文献 → 循证医学综合解读"""
import json, requests, argparse, os
from datetime import datetime
from pathlib import Path

WIKI = Path.home() / "wiki"


def get_key(path, default=None):
    try: return json.load(open(path))
    except: return default or {}


def build_prompt(analysis_path, lit_path):
    a, l = get_key(analysis_path, {}), get_key(lit_path, {})
    corr = a.get("correlation_matrix", {})
    abnormal = a.get("abnormal_summary", {})

    abn_items = [f"- {m}: 异常{v.get('abnormal_dates',[])[0] if v.get('abnormal_dates') else ''}, n={v.get('n_abnormal',0)}"
                 for m, v in abnormal.items() if isinstance(v, dict) and v.get("n_abnormal", 0) > 0]
    strong = [f"- {p}: r={v:.3f}" for p, v in corr.items() if isinstance(v, (int, float)) and abs(v) >= 0.9]
    papers = l.get("all_papers", [])[:8]
    abstracts = "\n\n---\n\n".join([f"PMID:{p['pmid']} | {p.get('title','')[:100]}\n摘要: {p.get('abstract','')[:400]}" for p in papers])

    return f"""你是医学检验科+重症医学科临床顾问，为慢性胰腺炎患者检验数据进行循证解读。

【异常指标】
{abn_items or "无"}

【强相关性（|r|≥0.9）】
{strong or "无"}

【文献证据】
{abstracts}

【解读要求】
1. CRP-WBC 分离的机制解释
2. RDW 持续升高的临床意义
3. MONO% 代偿的免疫学意义
4. 下一步循证建议（细菌 vs 病毒/免疫抑制）
5. 预后判断

中文回答，引用 PMID。"""


def call_deepseek(prompt):
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not key:
        env = Path.home() / ".hermes" / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("DEEPSEEK_API_KEY="): key = line.split("=", 1)[1].strip()
    if not key: return "❌ 未设置 DEEPSEEK_API_KEY"

    resp = requests.post("https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "deepseek-chat",
              "messages": [{"role": "system", "content": "你是医学检验科+重症医学科临床顾问。"},
                           {"role": "user", "content": prompt}],
              "temperature": 0.3, "max_tokens": 1500},
        timeout=60)
    return resp.json()["choices"][0]["message"]["content"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--patient-id"); p.add_argument("--analysis"); p.add_argument("--lit"); p.add_argument("--out")
    args = p.parse_args()

    wiki_data = WIKI / "data"
    if args.patient_id:
        pd = wiki_data / args.patient_id
        args.analysis = args.analysis or str(pd / "analysis_results.json")
        args.lit = args.lit or str(pd / "literature_results.json")
        args.out = args.out or str(pd / "literature_interpretation.json")

    prompt = build_prompt(args.analysis, args.lit)
    response = call_deepseek(prompt)

    out = {"generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "model": "deepseek-chat", "response": response}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"✅ 解读完成 → {args.out}")


if __name__ == "__main__":
    main()
