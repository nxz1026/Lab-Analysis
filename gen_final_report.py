#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成最终综合临床报告 - 调用 DeepSeek API"""
import json, requests, argparse, os
from pathlib import Path


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
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return ""


def main():
    args = parse_args()
    patient_id = args.patient_id
    import os
    ts = os.environ.get("ANALYSIS_TS", patient_id)

    DEEPSEEK_API_KEY = load_env_key("DEEPSEEK_API_KEY")
    if not DEEPSEEK_API_KEY:
        print("❌ 未找到 DEEPSEEK_API_KEY"); return

    data_dir = Path.home() / "wiki" / "data" / ts
    output_path = data_dir / "final_integrated_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 前置检查：核心输入文件是否存在
    required = [
        data_dir / "lab_metrics.json",
        data_dir / "analysis_results.json",
        data_dir / "literature_results.json",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        print(f"⚠️  以下前置文件不存在，将使用内置默认数据：")
        for p in missing:
            print(f"   - {p}")

    USER_PROMPT = f"""你是资深临床医学专家，请为患者聂聃（38岁男性，ID:Y00002207707）生成最终综合临床诊断报告。

【说明】以下数据来自 pipeline 各步骤汇总，请生成结构化报告。

【请依次阅读以下数据文件，未找到的文件请注明"数据暂缺"】：
1. 检验指标时序数据：/root/wiki/data/{patient_id}/lab_metrics.json
2. 统计分析结果：/root/wiki/data/{patient_id}/analysis_results.json（或 .md）
3. 文献检索结果：/root/wiki/data/{patient_id}/literature_results.json
4. 循证医学解读：/root/wiki/data/{patient_id}/literature_interpretation.json（或 .md）
5. MRI影像AI分析（如有）：/root/wiki/data/{patient_id}/mri_report_check_results.json

如上述文件不存在，请基于以下已汇总的核心信息生成报告：

【检验数据（2026-03-24 ~ 2026-04-14）】
日期       hs-CRP  CRP     WBC     NEUT#   MONO%   RDW-SD  PCT     PLT
03-24     2.78    —       —       —       —       —       —       —
03-30     1.41    10.00   5.66    3.49    6.70    46.90   0.16    154
04-08     10.00↑  17.44↑  3.04↓   1.52↓   17.80↑  50.60↑  0.17    153
04-14     1.82    —       —       —       —       52.50↑  0.33↑   —

【MRI影像（2026-04-11，检查编号Y00002207707）】
上腹部(肝胆胰脾)平扫+增强扫描+胰胆管薄层扫描
- 肝脏：肝右后叶上段2.2cm异常信号，考虑感染性病变，较前明显缩小
- 胰腺：胰管支架置入后，主胰管扩张（最宽1.0cm），胰头稍大
- 胆道：肝内胆管扩张，胆囊体积增大
- 右肾下份囊肿（1.5cm）

请生成【最终综合临床诊断报告】，结构如下：

# 最终综合临床诊断报告
**患者**：聂聃 | 男 | 38岁 | 检查编号：Y00002207707
**报告日期**：2026年5月1日
**数据来源**：MRI影像报告（2026-04-11）+ 检验数据（2026-03-24~04-14）

## 一、患者基本信息与就诊背景

## 二、检验数据与炎症状态综合分析

## 三、MRI影像学综合分析

## 四、多学科联合诊断意见

## 五、核心诊断结论与鉴别诊断

## 六、行动计划（紧急🔴 / 重要🟡 / 常规🟢）

## 七、随访与监测计划

## 八、预后评估

要求：专业清晰，中文输出；不生成具体药物处方或手术建议；各部分内容充实"""

    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是一个无害的医学资料分析助手，基于提供的患者数据生成结构化临床报告。"},
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
    print(f"Tokens: {usage.get('total_tokens', 'N/A')} (input={usage.get('prompt_tokens','')}, output={usage.get('completion_tokens','')})")
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
