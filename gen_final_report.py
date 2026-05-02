#!/usr/bin/env python3
"""生成最终综合临床报告 - 调用 DeepSeek API"""
import json, requests, argparse, os
from pathlib import Path

WIKI = Path.home() / "wiki"


def get_api_key(name):
    if v := os.environ.get(name): return v
    env = Path.home() / ".hermes" / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith(f"{name}="): return line.split("=", 1)[1].strip()
    return ""


def main():
    p = argparse.ArgumentParser(); p.add_argument("--patient-id", required=True); args = p.parse_args()
    pid = args.patient_id
    key = get_api_key("DEEPSEEK_API_KEY")
    if not key: print("❌ 未找到 DEEPSEEK_API_KEY"); return

    out = WIKI / "data" / pid / "final_integrated_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    # 读取各步骤数据文件
    def read(path):
        try: return Path(path).read_text(encoding="utf-8")[:3000]
        except: return "数据暂缺"

    lab_json = read(WIKI / "data" / pid / "lab_metrics.json")
    analysis = read(WIKI / "data" / pid / "analysis_results.json")
    lit = read(WIKI / "data" / pid / "literature_results.json")
    interp = read(WIKI / "data" / pid / "literature_interpretation.json")
    mri = read(WIKI / "data" / pid / "mri_report_check_results.json")

    prompt = f"""你是资深临床医学专家，请为患者聂聃（38岁男性，ID:Y00002207707）生成最终综合临床诊断报告。

【数据汇总】
1. 检验指标: {lab_json[:500]}
2. 统计分析: {analysis[:500]}
3. 文献检索: {lit[:500]}
4. 循证解读: {interp[:500]}
5. MRI影像: {mri[:500]}

【报告结构】
# 最终综合临床诊断报告
**患者**: 聂聃 | 男 | 38岁 | 检查编号：Y00002207707 | **报告日期**: 2026年5月1日

## 一、患者基本信息与就诊背景
## 二、检验数据与炎症状态综合分析
## 三、MRI影像学综合分析
## 四、多学科联合诊断意见
## 五、核心诊断结论与鉴别诊断
## 六、行动计划（紧急🔴 / 重要🟡 / 常规🟢）
## 七、随访与监测计划
## 八、预后评估

要求：专业清晰，中文输出；不生成具体药物处方或手术建议；各部分内容充实"""

    resp = requests.post("https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat",
              "messages": [{"role": "system", "content": "你是一个医学资料分析助手。"},
                           {"role": "user", "content": prompt}],
              "max_tokens": 5000, "temperature": 0.3},
        timeout=180)

    result = resp.json()
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

    if content:
        out.write_text(content, encoding="utf-8")
        print(f"✅ 报告已保存: {out}")
        print(f"Tokens: {result.get('usage', {}).get('total_tokens', 'N/A')}")
    else:
        print("❌ 生成失败:", json.dumps(result, ensure_ascii=False)[:500])


if __name__ == "__main__":
    main()
