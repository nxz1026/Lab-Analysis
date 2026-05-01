#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成最终综合临床报告 - 调用 DeepSeek API"""
import json, requests

DEEPSEEK_API_KEY = "sk-6022d79d153c43308514bf235914eba6"

SYSTEM_PROMPT = "你是一个无害的医学资料分析助手，基于提供的患者数据生成结构化临床报告。"
USER_PROMPT = """你是资深临床医学专家，请为患者聂聃（38岁男性，ID:Y00002207707）生成最终综合临床诊断报告。

【一、MRI纸质报告 - 2026-04-11，检查编号Y00002207707】
检查项目：上腹部(肝胆胰脾)平扫+增强扫描+胰胆管薄层扫描
影像所见：
1. 肝脏：肝右后叶上段长径约2.2cm异常信号影，T1稍低、T2及STIR稍高，增强扫描少许点片状弱强化，考虑感染性病变，较前明显缩小
2. 胰腺：「胰管支架置入后」，胰腺实质萎缩，周围脂肪间隙稍模糊，主胰管扩张程度较前明显，最宽约1.0cm，胰头稍大，胆总管胰腺段显示不清
3. 胆道：肝内胆管扩张，胆囊体积增大
4. 脾脏：体积不大
5. 肾脏：右肾下份囊肿，长径约1.5cm

【二、MRI影像AI印证分析结果 - Qwen3-VL-235B分析6个序列】
AI从858张MRI图像中选取6个关键序列进行了印证分析：
- T2/扩散加权序列：肝右后叶S7段椭圆形高信号（DWI受限），印证感染性病变 ✅
- 动脉期序列：胰头横径28mm（增大），胆总管胰腺段信号中断，完全印证 ✅
- 门脉期序列：肝内胆管"枯树枝征"扩张，胆囊横径4.8cm（增大），完全印证 ✅
- MRCP薄层序列：胰管内支架影，印证支架置入状态 ✅
- 扩散加权DWI：肝右后叶高信号，印证感染性病变 ✅
- 延迟增强序列：右肾下极1.5cm类圆形高信号，边界锐利，完全印证 ✅

AI补充发现：胰腺区域DWI高信号（可能为支架相关性胰腺炎），肝脏散在点状高信号（需警惕血管瘤或微转移）

结论：5个关键发现中4个完全印证，1个因序列特性有评估局限；纸质报告与影像高度吻合；无矛盾点

【三、检验数据综合分析报告 - 2026-03-24 ~ 2026-04-14，共4份报告】

核心指标：
日期       hs-CRP  CRP     WBC     NEUT#   MONO%   RDW-SD  PCT     PLT
03-24     2.78    —       —       —       —       —       —       —
03-30     1.41    10.00   5.66    3.49    6.70    46.90   0.16    154
04-08     10.00↑  17.44↑  3.04↓   1.52↓   17.80↑  50.60↑  0.17    153
04-14     1.82    —       —       —       —       52.50↑  0.33↑   —

关键发现：
1. CRP-WBC反向分离（r=-1.000）：CRP升高但WBC/NEUT#下降，提示骨髓免疫应答受损，高度怀疑免疫抑制或病毒/胞内菌感染，不符合典型细菌感染模式
2. 急性炎症事件：4月8日CRP 17.44，hs-CRP>10，明确急性加重；4月14日回落至1.82，治疗有效但未完全缓解
3. 炎症性贫血进行中：RDW-SD从46.9持续升至52.5（参考上限50），与CRP完美正相关，提示炎症驱动红系生成抑制
4. 血小板消耗风险：PLT与CRP负相关（r=-1.000），需排除DIC
5. 脓毒症免疫麻痹模式：MONO%升至17.8%，CRP↑+WBC↓+MONO%↑符合

循证依据（PMID）：
- PMID:27592340：CRP-WBC分离提示免疫状态复杂，脓毒症生物标志物需重新评估
- PMID:35942475：RDW是炎症性贫血独立预后因子，与CRP正相关
- PMID:38037118：G-菌脓毒症CRP/PCT显著高于G+菌
- PMID:39031283：RDW与炎症、氧化应激、心血管预后密切相关
- PMID:40281050：RDW是90天死亡率独立预测因子（OR=1.46）

【四、已生成的临床建议 - 2026-05-01】
紧急行动（本周内）：血培养×2套+病毒PCR（EBV/CMV/流感）；凝血四项+D-二聚体（排除DIC）；PCT动态监测
重要行动（两周内）：铁蛋白+B12+叶酸+血清铁（鉴别RDW升高原因）；腹部增强CT（评估胰腺炎活动性）
监测计划：hs-CRP每周1次（目标<1.0），WBC+NEUT#每周1次（目标WBC>4.0），RDW每2周1次（目标<50fL）

请生成【最终综合临床诊断报告】，结构如下，严格按此格式：

# 最终综合临床诊断报告
**患者**：聂聃 | 男 | 38岁 | 检查编号：Y00002207707
**报告日期**：2026年5月1日
**数据来源**：MRI影像报告（2026-04-11）+ 检验数据（2026-03-24~04-14）+ AI影像印证分析

## 一、患者基本信息与就诊背景

## 二、检验数据与炎症状态综合分析

## 三、MRI影像学综合分析（纸质报告 + AI印证结果）

## 四、多学科联合诊断意见（检验科 + 影像科 + 临床）

## 五、核心诊断结论与鉴别诊断

## 六、行动计划（紧急 / 重要 / 常规）

## 七、随访与监测计划

## 八、预后评估

---
要求：
- 专业清晰，中文输出
- 紧急程度用🔴（紧急）/🟡（重要）/🟢（常规）标注
- 不生成具体药物处方或手术建议
- 各部分内容充实，言之有物"""

resp = requests.post(
    "https://api.deepseek.com/chat/completions",
    headers={
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    },
    json={
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
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
    output_path = "/root/wiki/data/final_integrated_report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\n报告已保存: {output_path}")
    print("\n" + "="*60)
    print(content)
else:
    print("[EMPTY CONTENT]")
    print(json.dumps(result, ensure_ascii=False)[:1000])
