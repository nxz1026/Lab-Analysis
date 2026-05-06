#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_lab_data.py — 从检验报告图片中提取完整检验指标并生成结构化文件

用法：
  python extract_lab_data.py --image /path/to/lab_report.jpg --patient-id 513229198801040014

功能：
  1. 使用 Qwen-VL 从检验报告图片中提取所有检验指标
  2. 生成 metadata.md（报告元信息）
  3. 生成 metrics.md（检验指标数据，YAML格式）
  4. 保存到 raw/patient_{ID}/papers/lab_report_{date}_{type}/ 目录
"""
import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

import requests


def is_valid_id_card(patient_id: str) -> bool:
    """验证是否为有效的身份证号格式（18位或15位数字，最后一位可能是X）"""
    if not patient_id:
        return False
    pattern = r'^\d{17}[\dXx]$|^\d{15}$'
    return bool(re.match(pattern, patient_id))


def validate_patient_id(patient_id: str, extracted_id: str = None, interactive: bool = False) -> str:
    """
    验证患者ID，如果不是身份证号则尝试使用AI提取的ID或要求用户输入
    
    Args:
        patient_id: 命令行传入的患者ID
        extracted_id: AI从图片中提取的患者ID（备选）
        interactive: 是否启用交互模式
    
    Returns:
        有效的患者ID，或者无法验证时返回 None
    """
    # 优先级1：命令行提供的有效身份证号
    if patient_id and is_valid_id_card(patient_id):
        return patient_id
    
    # 优先级2：AI提取的有效身份证号
    if extracted_id and is_valid_id_card(extracted_id):
        print(f"[INFO] 输入的ID无效或未提供，使用AI提取的ID: {extracted_id}")
        return extracted_id
    
    # 优先级3：都没有有效身份证号
    if not patient_id and not extracted_id:
        print("[WARNING] 未提供患者ID，且AI未能从图片中识别到任何ID")
    elif patient_id and not is_valid_id_card(patient_id):
        print(f"[WARNING] 患者ID '{patient_id}' 不是有效的身份证号格式")
        if extracted_id:
            print(f"[WARNING] AI提取的ID '{extracted_id}' 也非有效身份证号")
    
    # 交互模式下要求用户输入
    if interactive:
        print("\n请选择:")
        print("  1. 手动输入正确的身份证号")
        print("  2. 放弃此数据")
        try:
            choice = input("请输入选择 (1/2): ").strip()
            
            if choice == "1":
                patient_id = input("请输入患者身份证号: ").strip()
                if is_valid_id_card(patient_id):
                    return patient_id
                else:
                    print(f"[ERROR] 输入的ID '{patient_id}' 无效，放弃此数据")
                    return None
            elif choice == "2":
                print("[INFO] 用户选择放弃此数据")
                return None
            else:
                print("[ERROR] 无效的选择，默认放弃此数据")
                return None
        except (EOFError, KeyboardInterrupt):
            print("\n[ERROR] 无法读取输入（非交互环境），放弃此数据")
            return None
    else:
        # 非交互模式：优先使用AI提取的ID（即使是病历号）
        if extracted_id:
            print(f"[WARNING] 未找到有效的身份证号，使用AI提取的ID: {extracted_id}")
            print(f"[HINT] 如果这是错误的ID，请使用 --patient-id 参数提供正确的身份证号")
            return extracted_id
        else:
            print("[ERROR] 无法获取任何患者ID，放弃此数据")
            print("[HINT] 请使用 --patient-id 参数提供患者ID")
            return None


WIKI_ROOT = Path(os.environ.get("WIKI_ROOT", Path.home() / "wiki"))


def get_api_key():
    """从环境变量获取 API Key"""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("未找到 OPENROUTER_API_KEY，请设置环境变量")
    return api_key


def encode_image_to_base64(image_path: Path) -> str:
    """将图片编码为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_lab_metrics(image_path: Path) -> dict:
    """
    使用 Qwen-VL 从检验报告图片中提取完整的检验指标数据
    
    返回：
    {
        "patient_id": "患者ID",
        "report_date": "YYYY-MM-DD",
        "report_type": "outpatient/inpatient",
        "department": "科室",
        "physician": "医生",
        "diagnosis": "诊断",
        "metrics": {
            "WBC": {"value": 7.5, "unit": "10^9/L", "ref_range": "3.5-9.5"},
            "RBC": {"value": 4.8, "unit": "10^12/L", "ref_range": "4.3-5.8"},
            ...
        }
    }
    """
    api_key = get_api_key()
    image_b64 = encode_image_to_base64(image_path)
    
    prompt = """你是医疗检验报告OCR和数据提取专家。请从这张检验报告图片中提取以下信息：

## 需要提取的信息：

### 1. 基本信息
- patient_id: 患者ID/诊疗卡号（纯数字）
- report_date: 报告日期（格式：YYYY-MM-DD）
- report_type: 门诊(outpatient)或住院(inpatient)
- department: 科室名称
- physician: 送检医生姓名
- diagnosis: 临床诊断（如果有）

### 2. 检验指标（重点！）
请提取所有血常规和炎症指标，包括但不限于：
- WBC (白细胞计数)
- RBC (红细胞计数)
- HGB (血红蛋白)
- HCT (红细胞压积)
- PLT (血小板计数)
- PCT (血小板压积)
- MCV, MCH, MCHC
- NEUT% (中性粒细胞百分比), NEUT# (绝对值)
- LYMPH% (淋巴细胞百分比), LYMPH# (绝对值)
- MONO% (单核细胞百分比), MONO# (绝对值)
- EO% (嗜酸性粒细胞百分比), EO# (绝对值)
- BASO% (嗜碱性粒细胞百分比), BASO# (绝对值)
- RDW-SD, RDW-CV
- MPV, PDW, P-LCR
- CRP, hs-CRP

对于每个指标，请提取：
- value: 数值（浮点数）
- unit: 单位
- ref_range: 参考范围（如"3.5-9.5"）

## 输出格式（严格的JSON）：

{
  "patient_id": "513229198801040014",
  "report_date": "2026-03-24",
  "report_type": "outpatient",
  "department": "门诊检验科",
  "physician": "张三",
  "diagnosis": "慢性胰腺炎",
  "metrics": {
    "WBC": {"value": 7.5, "unit": "10^9/L", "ref_range": "3.5-9.5"},
    "RBC": {"value": 4.8, "unit": "10^12/L", "ref_range": "4.3-5.8"},
    "HGB": {"value": 145, "unit": "g/L", "ref_range": "130-175"}
  }
}

## 重要提示：
1. 如果某个指标不存在，不要在metrics中包含它
2. 数值必须是数字类型，不要带单位
3. 参考范围保持原始格式（如"3.5-9.5"或"<10"）
4. 只返回JSON，不要其他文字
5. 仔细识别所有指标，不要遗漏
"""

    # 模型列表：优先免费，失败后切换到付费
    models_to_try = [
        ("qwen/qwen-2.5-vl-72b-instruct", "免费"),  # OpenRouter 免费模型
        ("qwen/qwen-vl-plus", "付费"),               # DashScope 付费模型（更稳定）
    ]
    
    last_error = None
    
    for model_name, model_type in models_to_try:
        try:
            print(f"[Vision] 尝试使用模型: {model_name} ({model_type})")
            
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                            {"type": "text", "text": prompt}
                        ]
                    }
                ],
                "max_tokens": 8000
            }
            
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/nxz1026/Lab-Analysis",
                    "X-Title": "Lab-Analysis Pipeline"
                },
                json=payload,
                timeout=180
            )
            resp.raise_for_status()
            
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # 清理Markdown代码块标记
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            # 尝试解析JSON
            try:
                result = json.loads(content)
                print(f"[OK] 成功提取 {len(result.get('metrics', {}))} 个检验指标 (使用 {model_type} 模型)")
                return result
            except json.JSONDecodeError as e:
                print(f"[WARNING] JSON解析失败: {e}")
                print(f"[INFO] 将尝试下一个模型...")
                last_error = f"JSON解析失败: {e}"
                continue
                
        except Exception as e:
            print(f"[WARNING] 模型 {model_name} 调用失败: {e}")
            print(f"[INFO] 将尝试下一个模型...")
            last_error = str(e)
            continue
    
    # 所有模型都失败
    print(f"[ERROR] 所有模型调用均失败。最后错误: {last_error}")
    return None


def generate_metadata_md(data: dict, validated_patient_id: str) -> str:
    """
    生成 metadata.md 文件内容
    
    Args:
        data: AI提取的数据
        validated_patient_id: 用户验证过的患者ID（优先使用）
    """
    # 优先使用用户验证过的ID，如果为空则使用AI提取的ID
    patient_id = validated_patient_id if validated_patient_id else data.get('patient_id', '')
    
    md = f"""| 字段 | 值 |
|------|-----|
| 患者ID | {patient_id} |
| 报告日期 | {data.get('report_date', '')} |
| 报告类型 | {data.get('report_type', '')} |
| 科室 | {data.get('department', '')} |
| 医生 | {data.get('physician', '')} |
| 诊断 | {data.get('diagnosis', '')} |
"""
    return md


def generate_metrics_md(data: dict) -> str:
    """生成 metrics.md 文件内容（YAML格式）"""
    metrics = data.get('metrics', {})
    
    yaml_lines = []
    for key, info in metrics.items():
        if isinstance(info, dict):
            value = info.get('value')
            if value is not None:
                yaml_lines.append(f"{key}: {value}")
    
    return "\n".join(yaml_lines) + "\n"


def save_structured_report(data: dict, patient_id: str) -> str:
    """
    保存结构化报告到 papers/lab_report_{date}_{type}/ 目录
    
    返回：保存的目录路径
    """
    # 导入患者ID脱敏函数
    from lab_analysis.patient_id import encode
    patient_id_obf = encode(patient_id)
    
    report_date = data.get('report_date', '').replace('-', '')
    report_type = data.get('report_type', 'unknown')
    
    # 创建目录：papers/lab_report_YYYYMMDD_type/
    report_dir = WIKI_ROOT / "raw" / f"patient_{patient_id_obf}" / "papers" / f"lab_report_{report_date}_{report_type}"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成 metadata.md（使用验证过的患者ID）
    metadata_md = generate_metadata_md(data, patient_id)
    metadata_path = report_dir / "metadata.md"
    metadata_path.write_text(metadata_md, encoding="utf-8")
    print(f"[OK] 已生成: {metadata_path.relative_to(WIKI_ROOT)}")
    
    # 生成 metrics.md
    metrics_md = generate_metrics_md(data)
    metrics_path = report_dir / "metrics.md"
    metrics_path.write_text(metrics_md, encoding="utf-8")
    print(f"[OK] 已生成: {metrics_path.relative_to(WIKI_ROOT)}")
    
    # 复制原始图片（可选）
    original_image = report_dir / "original_image.jpg"
    if not original_image.exists():
        import shutil
        # 假设原始图片在 lab/ 目录下
        lab_dir = WIKI_ROOT / "raw" / f"patient_{patient_id_obf}" / "lab"
        if lab_dir.exists():
            for img_file in lab_dir.glob(f"*{report_date}*"):
                if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    shutil.copy2(img_file, original_image)
                    print(f"[OK] 已复制原始图片: {original_image.relative_to(WIKI_ROOT)}")
                    break
    
    return str(report_dir.relative_to(WIKI_ROOT))


def main():
    parser = argparse.ArgumentParser(description="从检验报告图片提取完整检验指标并生成结构化文件")
    parser.add_argument("--image", "-i", required=True, type=Path, help="检验报告图片路径")
    parser.add_argument("--patient-id", type=str, default="", help="患者身份证号（可选，如果不提供则使用AI提取的ID）")
    parser.add_argument("--no-interactive", action="store_true", help="禁用交互模式（当ID无效时直接放弃数据）")
    args = parser.parse_args()
    
    # 默认启用交互模式，除非显式指定 --no-interactive
    interactive = not args.no_interactive
    
    image_path = args.image
    patient_id = args.patient_id
    
    if not image_path.exists():
        print(f"[ERROR] 文件不存在: {image_path}")
        return 1
    
    print("=" * 60)
    print("检验报告数据结构化提取工具")
    print("=" * 60)
    print(f"图片路径: {image_path.name}")
    print(f"患者ID: {patient_id if patient_id else '(未提供，将使用AI提取)'}")
    print(f"交互模式: {'是' if interactive else '否（无效ID将直接放弃）'}")
    print(f"工作区: {WIKI_ROOT}")
    print("=" * 60)
    
    # 步骤1：使用Qwen-VL提取数据
    print("\n[步骤1] 调用 Qwen-VL 提取检验指标...")
    data = extract_lab_metrics(image_path)
    
    if not data:
        print("[ERROR] 数据提取失败")
        return 1
    
    # 步骤2：验证患者ID（使用AI提取的ID作为备选）
    print("\n[步骤2] 验证患者ID...")
    extracted_id = data.get('patient_id')
    validated_id = validate_patient_id(patient_id, extracted_id, interactive)
    if not validated_id:
        print("[ERROR] 患者ID验证失败，终止处理")
        return 1
    patient_id = validated_id
    print(f"[OK] 患者ID验证通过: {patient_id}")
    
    # 步骤3：生成结构化文件
    print("\n[步骤3] 生成结构化报告文件...")
    saved_dir = save_structured_report(data, patient_id)
    
    # 步骤4：显示结果摘要
    print("\n" + "=" * 60)
    print("提取完成！")
    print("=" * 60)
    print(f"保存位置: {saved_dir}")
    print(f"报告日期: {data.get('report_date')}")
    print(f"报告类型: {data.get('report_type')}")
    print(f"提取指标数: {len(data.get('metrics', {}))}")
    print(f"\n主要指标:")
    for key in ['WBC', 'RBC', 'HGB', 'PLT', 'CRP', 'hs-CRP']:
        if key in data.get('metrics', {}):
            info = data['metrics'][key]
            print(f"  {key}: {info.get('value')} {info.get('unit', '')}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
