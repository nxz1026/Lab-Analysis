#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单独修复 mri_analyzer 训练（不强制 anatomical_localization 非空）"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import dspy

lm = dspy.LM(
    model="deepseek/deepseek-chat",
    api_key=os.environ["DEEPSEEK_API_KEY"],
    api_base="https://api.deepseek.com/v1",
    max_tokens=4000,
)
dspy.configure(lm=lm)

from lab_analysis.dspy_modules.mri_analyzer import MRIAnalysisModule


# 收集样本
def collect_mri_samples():
    samples = []
    data_root = project_root / "data" / "846552421134373347"
    for ts_dir in sorted(data_root.iterdir()):
        if not ts_dir.is_dir():
            continue
        mri_json = ts_dir / "03_literature" / "mri_report_check_results.json"
        if not mri_json.exists():
            mri_json = ts_dir / "03_literature" / "mri_analysis_results.json"
        if not mri_json.exists():
            continue
        with open(mri_json, encoding="utf-8") as f:
            mri_data = json.load(f)
        report_findings = (
            mri_data.get("report_findings", "")
            or mri_data.get("paper_report_text", "")
            or "胰腺体尾部萎缩，伴主胰管不规则扩张，符合慢性胰腺炎表现"
        )

        for r in mri_data.get("results", []):
            if r.get("status") != "success":
                continue
            # 解析 analysis 字段（可能是字符串或 array of {text}）
            analysis = r.get("analysis", "")
            if isinstance(analysis, list):
                # 取每个 dict 的 text 字段
                analysis_text = "\n".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in analysis
                )
            else:
                analysis_text = str(analysis)

            # 尝试从分析文本中提取各字段（粗略解析）
            al = ""
            imf = analysis_text
            ce = "一致"
            af = "无"
            if "### 1. 解剖定位" in analysis_text or "解剖定位" in analysis_text:
                # 简单分段
                import re

                m = re.search(r"解剖定位[：:]\s*([^\n]+)", analysis_text)
                if m:
                    al = m.group(1).strip()
                m2 = re.search(
                    r"影像所见[：:]\s*(.+?)(?=###|印证评价|补充发现|总结|$)",
                    analysis_text,
                    re.DOTALL,
                )
                if m2:
                    imf = m2.group(1).strip()[:500]
                m3 = re.search(
                    r"印证评价[：:]*\s*(.+?)(?=###|补充发现|总结|$)", analysis_text, re.DOTALL
                )
                if m3:
                    ce = m3.group(1).strip()[:200]
                m4 = re.search(r"补充发现[：:]*\s*(.+?)(?=###|总结|$)", analysis_text, re.DOTALL)
                if m4:
                    af = m4.group(1).strip()[:200]

            samples.append(
                {
                    "image_description": r.get("seq_desc", ""),
                    "report_findings": report_findings[:2000],
                    "clinical_context": "慢性胰腺炎患者，2026-04-11 上腹部 MRI",
                    "anatomical_localization": al or r.get("seq_desc", ""),
                    "imaging_findings": imf or analysis_text[:500],
                    "consistency_evaluation": ce,
                    "additional_findings": af,
                    "confidence_score": float(r.get("confidence", 0.9)),
                }
            )
    return samples


raw = collect_mri_samples()
print(f"[收集] MRI 样本数: {len(raw)}")

# 至少 3 个
while len(raw) < 3:
    raw.append(dict(raw[0]))
print(f"[扩充] 训练样本数: {len(raw)}")

# 转 Example
trainset = []
for d in raw:
    ex = dspy.Example(**d).with_inputs("image_description", "report_findings", "clinical_context")
    trainset.append(ex)


def simple_metric(example, pred, trace=None):
    try:
        al = getattr(pred, "anatomical_localization", "") or ""
        imf = getattr(pred, "imaging_findings", "") or ""
        ce = getattr(pred, "consistency_evaluation", "") or ""
        cs = getattr(pred, "confidence_score", 0)
        return len(al) >= 3 and len(imf) >= 50 and len(ce) >= 3 and 0.5 <= cs <= 1.0
    except Exception:
        return False


print(f"\n[训练] mri_analyzer: {len(trainset)} 个 Example")
optimizer = dspy.teleprompt.BootstrapFewShot(
    metric=simple_metric,
    max_bootstrapped_demos=2,
    max_labeled_demos=2,
)
compiled = optimizer.compile(student=MRIAnalysisModule(), trainset=trainset)

out_dir = project_root / "models" / "dspy"
out_dir.mkdir(parents=True, exist_ok=True)
save_path = out_dir / "mri_analyzer_compiled.json"
compiled.save(save_path)
print(f"[保存] {save_path}")

for name, pred in compiled.named_predictors():
    print(f"  {name}: demos={len(pred.demos) if hasattr(pred, 'demos') else 0}")
