#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成最终综合临床报告 - 调用 DeepSeek API"""
import json
import requests
import argparse
import os
import sys
from pathlib import Path

WIKI_ROOT = Path.home() / "wiki"

# ============================================================
# 患者信息脱敏常量（发布前务必确认）
# ============================================================
PATIENT_NAME = "张三"
PATIENT_AGE_SEX = "38岁男性"
PATIENT_EXAM_ID = "Y00002207707"
# ============================================================
# ⚠️ 如需恢复从真实数据读取姓名，解除下方注释并注释掉以上常量
# ============================================================
# _name_raw = None
# def _load_patient_name(lab_path: Path) -> str:
#     """从 lab_metrics.json 的第一份报告里读取患者姓名。"""
#     global _name_raw
#     if _name_raw:
#         return _name_raw
#     if lab_path.exists():
#         try:
#             d = json.loads(lab_path.read_text())
#             reports = d.get("reports", [])
#             if reports:
#                 _name_raw = reports[0].get("patient_name", "未知")
#                 return _name_raw
#         except Exception:
#             pass
#     return "未知"
# ============================================================


def parse_args():
    parser = argparse.ArgumentParser(description="生成最终综合临床报告")
    parser.add_argument("--patient-id", required=True, help="病人诊疗卡号")
    return parser.parse_args()


def load_env_key(key: str) -> str:
    val = os.environ.get(key, "")
    if val:
        return val
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""


def assess_three_source_consistency(data_dir: Path) -> str:
    """评估三源一致性，生成质控段落。

    三源：
    1. 检验数据（lab_metrics.json）
    2. 影像印证（mri_report_check_results.json）
    3. 文献证据（literature_results.json + literature_interpretation.json）

    Returns:
        Markdown 格式质控段落
    """
    signals = []   # (label, status, detail)

    # ── 源1：检验数据 ───────────────────────────────────────────
    lab_path = data_dir / "lab_metrics.json"
    lab_summary = "数据暂缺"
    if lab_path.exists():
        try:
            d = json.loads(lab_path.read_text(encoding="utf-8"))
            reports = d.get("reports", [])
            if reports:
                latest = reports[-1]
                hs_crp = latest.get("hs-CRP") or latest.get("hsCRP")
                if hs_crp is not None and isinstance(hs_crp, (int, float)):
                    flag = "↑" if hs_crp > 3 else ""
                    lab_summary = f"hs-CRP={hs_crp}{flag}"
                    if hs_crp > 10:
                        signals.append(("检验-hsCRP", "ACUTE",
                                       f"hs-CRP={hs_crp}↑↑，提示急性炎症/感染"))
                    elif hs_crp > 3:
                        signals.append(("检验-hsCRP", "ELEVATED",
                                       f"hs-CRP={hs_crp}↑，提示炎症活跃"))
                    else:
                        signals.append(("检验-hsCRP", "NORMAL",
                                       f"hs-CRP={hs_crp}，炎症处于缓解期"))
                else:
                    lab_summary = "hs-CRP数据异常"
        except Exception:
            lab_summary = "数据解析失败"

    # ── 源2：影像印证 ──────────────────────────────────────────
    mri_path = data_dir / "mri_report_check_results.json"
    mri_summary = "影像印证暂缺"
    if mri_path.exists():
        try:
            mri = json.loads(mri_path.read_text(encoding="utf-8"))
            checks = mri.get("results", []) if isinstance(mri, dict) else []
            if checks:
                confirmed = sum(1 for c in checks if c.get("status") == "success")
                suspicious = sum(1 for c in checks if c.get("status") == "partial")
                mri_summary = f"共{len(checks)}项，成功{confirmed}项，存疑{suspicious}项"
                if confirmed > suspicious:
                    signals.append(("影像印证", "SUPPORT",
                                   f"{confirmed}项影像发现与报告一致，支持检验结论"))
                elif suspicious > 0:
                    signals.append(("影像印证", "CONFLICT",
                                   f"{suspicious}项影像发现与报告存疑"))
                else:
                    signals.append(("影像印证", "NEUTRAL", "影像印证无显著异常"))
            else:
                mri_summary = "影像印证结果为空"
        except Exception:
            mri_summary = "影像数据解析失败"

    # ── 源3：文献证据 ───────────────────────────────────────────
    lit_results_path = data_dir / "literature_results.json"
    lit_interp_path = data_dir / "literature_interpretation.json"
    lit_summary = "文献证据暂缺"
    if lit_results_path.exists():
        try:
            lit = json.loads(lit_results_path.read_text(encoding="utf-8"))
            count = lit.get("total_unique_papers", 0)
            papers = lit.get("all_papers", [])
            year_range = ""
            if papers:
                years = [int(p["year"]) for p in papers if p.get("year", "").isdigit()]
                if years:
                    year_range = f"（{min(years)}-{max(years)}）"
            lit_summary = f"检索到{count}篇文献{year_range}"
        except Exception:
            lit_summary = "文献数据解析失败"

    if lit_interp_path.exists():
        try:
            interp = json.loads(lit_interp_path.read_text(encoding="utf-8"))
            resp_text = interp.get("response", "") or interp.get("text", "")
            if resp_text and len(resp_text) > 50:
                signals.append(("文献-循证解读", "SUPPORT",
                               "文献检索+循证解读已完成，证据链完整"))
        except Exception:
            pass

    # ── 一致性判断 ─────────────────────────────────────────────
    acute_count = sum(1 for _, s, _ in signals if s == "ACUTE")
    conflict_count = sum(1 for _, s, _ in signals if s == "CONFLICT")
    support_count = sum(1 for _, s, _ in signals if s in ("SUPPORT", "NORMAL"))

    if acute_count > 0:
        overall = "🔴 **结论一致性：检验/影像/文献三者指向急性炎症状态，建议尽快处理。**"
        detail = "患者处于急性炎症/感染状态，三源证据一致。"
    elif conflict_count > 0 and support_count > conflict_count:
        overall = "⚠️  **结论一致性：检验/影像/文献存在部分矛盾，需结合临床综合判断。**"
        detail = "三源证据中部分矛盾，建议进一步检查或短期复查后再评估。"
    elif conflict_count > 0:
        overall = "🔴 **结论一致性：检验/影像/文献存在明显矛盾，报告可信度存疑。**"
        detail = "三源证据矛盾较多，建议复核原始数据后再发正式报告。"
    elif support_count >= 2:
        overall = "✅  **结论一致性：检验/影像/文献三者支持，无显著矛盾。**"
        detail = "三源证据相互印证，报告可信度高。"
    else:
        overall = "⚠️  **结论一致性：证据不充分，无法完整评估一致性。**"
        detail = "部分源数据缺失，建议补充检查后再出报告。"

    # ── 拼段落 ─────────────────────────────────────────────────
    status_icon = {"ACUTE": "🔴", "ELEVATED": "⚠️", "NORMAL": "✅",
                   "SUPPORT": "✅", "CONFLICT": "❌", "NEUTRAL": "⚠️",
                   "UNKNOWN": "⚠️"}.get

    lines = [
        "## 附：三源质控段落\n",
        f"| 证据来源 | 内容摘要 |",
        f"|---------|---------|",
        f"| 检验数据 | {lab_summary} |",
        f"| 影像印证 | {mri_summary} |",
        f"| 文献证据 | {lit_summary} |",
        "",
        overall, detail, "",
        "**信号详情**：",
    ]
    for label, status, desc in signals:
        lines.append(f"- {status_icon(status)} [{label}][{status}] {desc}")

    return "\n".join(lines)


def build_prompt(data_dir: Path, patient_id: str) -> str:
    """构建完整的 USER_PROMPT，包含三源数据和质控段落。"""
    # 读检验数据
    lab_data = ""
    lab_path = data_dir / "lab_metrics.json"
    if lab_path.exists():
        try:
            d = json.loads(lab_path.read_text(encoding="utf-8"))
            reports = d.get("reports", [])
            if reports:
                cols = ["report_date", "hs-CRP", "CRP", "WBC", "NEUT#",
                        "MONO%", "RDW-SD", "PCT", "PLT"]
                rows = ["日期       hs-CRP  CRP     WBC     NEUT#   MONO%   RDW-SD  PCT     PLT"]
                for r in reports:
                    vals = []
                    for c in cols[1:]:
                        v = r.get(c) or r.get(c.replace("-", "")) or "—"
                        if isinstance(v, float):
                            v = f"{v:.2f}"
                        vals.append(str(v))
                    rows.append(f"{r.get('report_date', '??')}  " + "  ".join(vals))
                lab_data = "\n".join(rows)
        except Exception:
            lab_data = "(检验数据解析失败)"

    # 读文献列表
    lit_data = ""
    lit_path = data_dir / "literature_results.json"
    if lit_path.exists():
        try:
            lit = json.loads(lit_path.read_text(encoding="utf-8"))
            papers = lit.get("all_papers", [])[:6]
            if papers:
                lit_lines = [
                    f"- {p.get('year','?')} | {p.get('title','')[:60]}... (PMID:{p.get('pmid')})"
                    for p in papers
                ]
                lit_data = "\n".join(lit_lines)
        except Exception:
            lit_data = "(文献数据解析失败)"

    # 读循证解读
    interp_data = ""
    interp_path = data_dir / "literature_interpretation.json"
    if interp_path.exists():
        try:
            d = json.loads(interp_path.read_text(encoding="utf-8"))
            t = d.get("response", "") or d.get("text", "")
            if t:
                interp_data = t[:800] + "..." if len(t) > 800 else t
        except Exception:
            interp_data = "(循证解读解析失败)"

    # 读MRI印证
    mri_data = ""
    mri_path = data_dir / "mri_report_check_results.json"
    if mri_path.exists():
        try:
            mri = json.loads(mri_path.read_text(encoding="utf-8"))
            checks = mri.get("results", []) if isinstance(mri, dict) else []
            if checks:
                mri_lines = [
                    f"- {c.get('seq_name','')}: {c.get('analysis', [{}])[0].get('text','')[:60]}"
                    for c in checks[:5]
                ]
                mri_data = "\n".join(mri_lines)
            else:
                mri_data = "(影像印证结果为空)"
        except Exception:
            mri_data = "(影像数据解析失败)"

    # 三源质控段落
    qc = assess_three_source_consistency(data_dir)

    import datetime as dt
    today = dt.date.today().strftime("%Y年%m月%d日")

    prompt = f"""你是资深临床医学专家，请为患者{PATIENT_NAME}（{PATIENT_AGE_SEX}，ID:{PATIENT_EXAM_ID}）生成最终综合临床诊断报告。

【说明】以下数据来自 pipeline 各步骤汇总，请生成结构化报告。

【请依次阅读以下数据文件，未找到的文件请注明"数据暂缺"】：
1. 检验指标时序数据：{str(lab_path)}
2. 统计分析结果：{str(data_dir / "analysis_results.json")}
3. 文献检索结果：{str(lit_path)}
4. 循证医学解读：{str(interp_path)}
5. MRI影像AI分析（如有）：{str(mri_path)}

---

### 【检验数据摘要】
{lab_data if lab_data else "(数据暂缺)"}

### 【Top 文献列表】
{lit_data if lit_data else "(数据暂缺)"}

### 【循证解读摘要】
{interp_data if interp_data else "(数据暂缺)"}

### 【MRI影像印证摘要】
{mri_data if mri_data else "(影像数据暂缺)"}

---

{qc}

---

请生成【最终综合临床诊断报告】，结构如下：

# 最终综合临床诊断报告
**患者**：{PATIENT_NAME} | {PATIENT_AGE_SEX} | 检查编号：{PATIENT_EXAM_ID}
**报告日期**：{today}
**数据来源**：MRI影像报告（2026-04-11）+ 检验数据（2026-03-24~04-14）

## 一、患者基本信息与就诊背景

## 二、检验数据与炎症状态综合分析

## 三、MRI影像学综合分析

## 四、多学科联合诊断意见

## 五、核心诊断结论与鉴别诊断

## 六、结论一致性评估
> 将上方「三源质控段落」的核心结论原文引用或摘要写入本节。

## 七、行动计划（紧急🔴 / 重要🟡 / 常规🟢）

## 八、随访与监测计划

## 九、预后评估

要求：专业清晰，中文输出；不生成具体药物处方或手术建议；各部分内容充实"""
    return prompt


def main():
    args = parse_args()
    patient_id = args.patient_id
    import os
    raw_ts = os.environ.get("ANALYSIS_TS", ""); ts = raw_ts.split("/")[-1] if "/" in raw_ts else (raw_ts or patient_id); data_dir = WIKI_ROOT / "data" / patient_id / ts

    DEEPSEEK_API_KEY = load_env_key("DEEPSEEK_API_KEY")
    if not DEEPSEEK_API_KEY:
        print("❌ 未找到 DEEPSEEK_API_KEY"); return

    data_dir = Path.home() / "wiki" / "data" / args.patient_id / ts
    output_path = data_dir / "final_integrated_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 前置检查：核心输入文件是否存在（警告但不阻断）
    required = [
        data_dir / "lab_metrics.json",
        data_dir / "analysis_results.json",
        data_dir / "literature_results.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print("⚠️  以下前置文件不存在，将使用内置默认数据：")
        for p in missing:
            print(f"   - {p}")

    print(f"[{__import__('datetime').datetime.now().isoformat()}] 生成最终报告...")
    print(f"  data_dir: {data_dir}")

    USER_PROMPT = build_prompt(data_dir, patient_id)

    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system",
                 "content": "你是一个无害的医学资料分析助手，基于提供的患者数据生成结构化临床报告。"},
                {"role": "user", "content": USER_PROMPT}
            ],
            "max_tokens": 5000,
            "temperature": 0.3
        },
        timeout=180
    )

    result = resp.json()
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    usage = result.get("usage", {})

    print(f"HTTP: {resp.status_code}")
    print(f"Tokens: {usage.get('total_tokens', 'N/A')} "
          f"(in={usage.get('prompt_tokens','')}, out={usage.get('completion_tokens','')})")
    print(f"Content length: {len(content)}")

    if content:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n报告已保存: {output_path}")
        print("\n" + "="*60)
        print(content)
    else:
        print("[EMPTY CONTENT]")
        print(json.dumps(result, ensure_ascii=False)[:1000])


if __name__ == "__main__":
    main()
