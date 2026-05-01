#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上腹部MRI报告印证明分析
对照纸质报告的5个关键发现，从各序列选取典型层面进行AI影像解读
"""

import base64, json, requests, os
from pathlib import Path
from datetime import datetime

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
if not DASHSCOPE_API_KEY:
    # 尝试从 ~/.hermes/.env 手动加载
    env_path = os.path.expanduser("~/.hermes/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("DASHSCOPE_API_KEY=") and not line.startswith("#"):
                    DASHSCOPE_API_KEY = line.split("=", 1)[1].strip().strip("'\"")
                    break
if not DASHSCOPE_API_KEY:
    raise RuntimeError("DASHSCOPE_API_KEY 未设置，请检查 ~/.hermes/.env")

API_BASE = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# 报告关键发现（来自纸质报告）
REPORT_FINDINGS = """
【纸质报告关键发现 - 2026-04-11】
1. 肝右后叶上段：长径约2.2cm异常信号影，T1稍低、T2及STIR稍高，增强扫描少许点片状弱强化，考虑感染性病变，较前明显缩小
2. 主胰管：扩张程度较前明显，最宽约1.0cm（「胰管支架置入后」状态）
3. 胰头：稍大，胆总管胰腺段显示不清
4. 胆道：肝内胆管扩张，胆囊体积增大
5. 右肾：下份囊肿，长径约1.5cm
"""

# 图像选择：序列名 → (选取逻辑, 选取层号)
IMAGE_SELECTIONS = {
    "seq_20260411143441": ("肝胆T2/扩散加权，72张，选中间层面约第37张", 37),
    "seq_20260411143750": ("动脉期，25张，选第13张（胰头区域）", 13),
    "seq_20260411143944": ("门脉期，25张，选第13张（胰头+肝门区域）", 13),
    "seq_20260411145424": ("胰胆管薄层MRCP，33张，选第17张（胰管+胆管）", 17),
    "seq_20260411144836": ("扩散加权DWI，72张，选第37张（肝右后叶区域）", 37),
    "seq_20260411144200": ("延迟增强，8张，选第5张（肝脏+肾区）", 5),
}

PROMPT_TEMPLATE = """你是一位资深放射科医生。请仔细分析这张上腹部MRI影像，并结合以下【纸质报告描述】进行印证分析。

【纸质报告描述】
{report_finding}

【本张影像信息】
- 序列: {seq_name}
- 扫描部位: 上腹部（肝胆胰脾）+ 胰胆管薄层
- 检查日期: 2026-04-11
- 患者: 聂聃，男，38岁
- 临床指征: 胰管支架置入后复查，腹痛待查

请完成以下分析：
1. 【解剖定位】这张图片大约在哪个层面（肝脏？胰腺？肾脏？其他？）
2. 【影像所见】详细描述可见的结构和信号特征
3. 【印证评价】对照纸质报告描述，判断该影像表现是否与报告一致？
   - 如果一致，说明印证点
   - 如果不一致或发现新问题，明确指出
4. 【补充发现】纸质报告未提及但影像可见的异常

请用专业医学影像语言描述，结论明确。"""


def image_to_base64(image_path: Path) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_single(image_path: Path, seq_name: str, seq_desc: str, finding: str) -> dict:
    """分析单张图片"""
    b64_img = image_to_base64(image_path)

    payload = {
        "model": "qwen3-vl-235b-a22b-thinking",
        "input": {
            "messages": [{
                "role": "user",
                "content": [
                    {"image": f"data:image/jpeg;base64,{b64_img}"},
                    {"text": PROMPT_TEMPLATE.format(
                        report_finding=finding,
                        seq_name=f"{seq_name}（{seq_desc}）"
                    )}
                ]
            }]
        },
        "parameters": {"max_tokens": 1024, "thinking": True}
    }

    headers = {
        "Authorization": f"Bearer {DASHSCOPE_API_KEY}",
        "Content-Type": "application/json"
    }

    print(f"\n{'='*60}")
    print(f"📷 分析: {seq_name} - {seq_desc}")
    print(f"   图片: {image_path.name}")

    resp = requests.post(API_BASE, headers=headers, json=payload, timeout=180)
    result = resp.json()

    if resp.status_code != 200:
        print(f"  ❌ HTTP {resp.status_code}: {result}")
        return {"status": "error", "seq": seq_name, "http_code": resp.status_code, "error": result}

    try:
        content = result["output"]["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = content[0].get("text", str(content))
        reasoning = result["output"]["choices"][0]["message"].get("reasoning_content", "")
        usage = result.get("usage", {})
    except Exception as e:
        print(f"  ❌ 解析失败: {e}")
        return {"status": "parse_error", "seq": seq_name, "raw": result}

    print(f"  ✅ 完成")
    if usage:
        print(f"  💰 Token使用: {usage}")

    return {
        "status": "success",
        "seq_name": seq_name,
        "seq_desc": seq_desc,
        "image_file": image_path.name,
        "analysis": content,
        "thinking": reasoning,
        "usage": usage
    }


def main():
    base = Path("/root/wiki/raw/imaging/2026-04-11_MRI_niedan")
    data_dir = Path("/root/wiki/data")
    data_dir.mkdir(exist_ok=True)

    print(f"\n[{datetime.now().isoformat()}] 上腹部MRI报告印证明分析")
    print(f"共分析 {len(IMAGE_SELECTIONS)} 个序列...\n")

    # 5个关键发现，对应序列分配
    findings_map = {
        "seq_20260411144836": REPORT_FINDINGS.split("1.")[1].split("2.")[0].strip(),  # 肝脏病灶
        "seq_20260411143441": "【见纸质报告第1点】肝右后叶上段异常信号影",
        "seq_20260411145424": REPORT_FINDINGS.split("2.")[1].split("3.")[0].strip(),  # 胰管扩张
        "seq_20260411143750": REPORT_FINDINGS.split("3.")[1].split("4.")[0].strip(),  # 胰头大
        "seq_20260411143944": REPORT_FINDINGS.split("4.")[1].split("5.")[0].strip(), # 胆道扩张
        "seq_20260411144200": REPORT_FINDINGS.split("5.")[1].strip(),                  # 右肾囊肿
    }

    results = []
    for seq_dir, (seq_desc, img_idx) in IMAGE_SELECTIONS.items():
        p = base / seq_dir
        if not p.exists():
            print(f"⚠️  目录不存在: {seq_dir}，跳过")
            continue

        imgs = sorted(p.glob("*.jpeg"))
        if len(imgs) < img_idx + 1:
            print(f"⚠️  {seq_dir} 只有{len(imgs)}张图，跳过")
            continue

        img_path = imgs[img_idx]
        finding_text = findings_map.get(seq_dir, "（综合分析）")

        r = analyze_single(img_path, seq_dir, seq_desc, finding_text)
        results.append(r)

        if r["status"] == "success":
            print(f"\n📋 分析结果 [{seq_dir}]:")
            print(f"{r['analysis'][:800]}")
            if r['analysis'][800:]:
                print(f"    ...(省略{len(r['analysis'])-800}字)")
        else:
            print(f"  ❌ 失败: {r.get('error', 'unknown')}")

        # 避免API限流，间隔1秒
        import time; time.sleep(1)

    # 保存结果
    output_path = data_dir / "mri_report_check_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "test_date": datetime.now().isoformat(),
            "model": "qwen3-vl-235b-a22b-thinking",
            "report_findings": REPORT_FINDINGS,
            "image_selections": {k: {"desc": v[0], "img_idx": v[1]} for k, v in IMAGE_SELECTIONS.items()},
            "results": results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n💾 结果已保存: {output_path}")

    # 生成摘要
    print("\n" + "="*60)
    print("📊 分析摘要")
    print("="*60)
    for r in results:
        if r["status"] == "success":
            print(f"\n✅ {r['seq_name']} ({r['seq_desc']})")
            # 截取前200字
            text = r['analysis'][:300]
            print(f"   {text}...")


if __name__ == "__main__":
    main()
