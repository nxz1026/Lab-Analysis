#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_lab_data.py — 从检验报告图片中提取完整检验指标并生成结构化文件

用法：
  python extract_lab_data.py --image /path/to/lab_report.jpg --id-card <身份证号>

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
import sys
import time
from pathlib import Path

from lab_analysis.llm_client import call_chat, load_api_key, parse_json_response
from lab_analysis.patient_id import encode, validate_id_card

WORK_ROOT = Path(os.environ.get("WORK_ROOT", Path.cwd()))


def encode_image_to_base64(image_path: Path) -> str:
    """将图片编码为 base64（自动转为RGB并压缩）"""
    from io import BytesIO

    from PIL import Image
    img = Image.open(image_path).convert("RGB")
    if max(img.size) > 2000:
        ratio = 2000 / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


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
    api_key = load_api_key("ZHIPU_API_KEY")
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
  "patient_id": "YOUR_PATIENT_ID",
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

    # 使用智谱AI GLM-4V-Flash模型
    model_name = "glm-4v-flash"
    model_type = "智谱AI"

    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        if attempt > 0:
            wait_time = 2 ** attempt
            print(f"[Vision] 等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)

        print(f"[Vision] 尝试使用模型: {model_name} ({model_type}) [尝试 {attempt + 1}/{max_retries}]")
        try:
            raw = call_chat(
                "zhipu",
                user_prompt=prompt,
                image_b64=image_b64,
                model=model_name,
                api_key=api_key,
                timeout=180,
            )
            result = parse_json_response(raw)
            print(f"[OK] 成功提取 {len(result.get('metrics', {}))} 个检验指标 (使用 {model_type} 模型)")
            return result
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON解析失败: {e}")
            print(f"[INFO] 原始响应: {raw[:500]}")
            last_error = f"JSON解析失败: {e}"
            continue
        except Exception as e:
            print(f"[ERROR] 模型调用失败: {e}")
            if "429" in str(e):
                print("[WARNING] 遇到速率限制，将增加等待时间")
            last_error = str(e)
            continue

    print(f"[ERROR] 所有 {max_retries} 次尝试均失败。最后错误: {last_error}")
    import traceback
    traceback.print_exc()
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
| 身份证号 | {patient_id} |
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
    patient_id_obf = encode(patient_id)
    
    report_date = data.get('report_date', '').replace('-', '')
    report_type = data.get('report_type', 'unknown')
    
    # 创建目录：papers/lab_report_YYYYMMDD_type/
    report_dir = WORK_ROOT / "raw" / f"patient_{patient_id_obf}" / "papers" / f"lab_report_{report_date}_{report_type}"
    report_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成 metadata.md（使用验证过的患者ID）
    metadata_md = generate_metadata_md(data, patient_id)
    metadata_path = report_dir / "metadata.md"
    metadata_path.write_text(metadata_md, encoding="utf-8")
    print(f"[OK] 已生成: {metadata_path.relative_to(WORK_ROOT)}")
    
    # 生成 metrics.md
    metrics_md = generate_metrics_md(data)
    metrics_path = report_dir / "metrics.md"
    metrics_path.write_text(metrics_md, encoding="utf-8")
    print(f"[OK] 已生成: {metrics_path.relative_to(WORK_ROOT)}")
    
    # 复制原始图片（可选）
    original_image = report_dir / "original_image.jpg"
    if not original_image.exists():
        import shutil
        # 假设原始图片在 lab/ 目录下
        lab_dir = WORK_ROOT / "raw" / f"patient_{patient_id_obf}" / "lab"
        if lab_dir.exists():
            for img_file in lab_dir.glob(f"*{report_date}*"):
                if img_file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    shutil.copy2(img_file, original_image)
                    print(f"[OK] 已复制原始图片: {original_image.relative_to(WORK_ROOT)}")
                    break
    
    return str(report_dir.relative_to(WORK_ROOT))


def main_with_args(args) -> bool:
    """
    使用给定的参数执行提取流程（可被其他模块调用）
    
    Args:
        args: argparse.Namespace 对象，包含 image, id_card, no_interactive
    
    Returns:
        是否成功
    """
    interactive = not args.no_interactive
    image_path = Path(args.image)
    id_card = getattr(args, "id_card", "") or ""
    
    if not image_path.exists():
        print(f"[ERROR] 文件不存在: {image_path}")
        return False
    
    print("=" * 60)
    print("检验报告数据结构化提取工具")
    print("=" * 60)
    print(f"图片路径: {image_path.name}")
    print(f"身份证号: {id_card if id_card else '(未提供，将使用AI提取)'}")
    print(f"交互模式: {'是' if interactive else '否（无效ID将直接放弃）'}")
    print(f"工作区: {WORK_ROOT}")
    print("=" * 60)
    
    try:
        # 步骤1：使用Qwen-VL提取数据
        print("\n[步骤1] 调用 Qwen-VL 提取检验指标...")
        data = extract_lab_metrics(image_path)
        
        if not data:
            print("[ERROR] 数据提取失败")
            return False
        
        # 步骤2：强制校验身份证号（使用AI提取的ID作为备选）
        print("\n[步骤2] 验证身份证号...")
        extracted_id = data.get('patient_id')
        validated_id = validate_id_card(id_card, extracted_id, interactive=interactive)
        if not validated_id:
            print("[ERROR] 身份证号验证失败，终止处理")
            return False
        id_card = validated_id
        print(f"[OK] 身份证号验证通过: {id_card}")
        
        # 步骤3：生成结构化文件
        print("\n[步骤3] 生成结构化报告文件...")
        saved_dir = save_structured_report(data, id_card)
        
        # 步骤4：显示结果摘要
        print("\n" + "=" * 60)
        print("提取完成！")
        print("=" * 60)
        print(f"保存位置: {saved_dir}")
        print(f"报告日期: {data.get('report_date')}")
        print(f"报告类型: {data.get('report_type')}")
        print(f"提取指标数: {len(data.get('metrics', {}))}")
        print("\n主要指标:")
        for key in ['WBC', 'RBC', 'HGB', 'PLT', 'CRP', 'hs-CRP']:
            if key in data.get('metrics', {}):
                info = data['metrics'][key]
                print(f"  {key}: {info.get('value')} {info.get('unit', '')}")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description="从检验报告图片提取完整检验指标并生成结构化文件")
    parser.add_argument("--image", "-i", required=True, type=Path, help="检验报告图片路径")
    parser.add_argument("--id-card", type=str, default="", help="患者身份证号(18位或15位，可选，不提供则使用AI提取的ID)")
    parser.add_argument("--no-interactive", action="store_true", help="禁用交互模式（当身份证号无效时直接放弃数据）")
    args = parser.parse_args()
    
    # 默认启用交互模式，除非显式指定 --no-interactive
    interactive = not args.no_interactive
    
    image_path = args.image
    id_card = args.id_card
    
    if not image_path.exists():
        print(f"[ERROR] 文件不存在: {image_path}")
        return 1
    
    print("=" * 60)
    print("检验报告数据结构化提取工具")
    print("=" * 60)
    print(f"图片路径: {image_path.name}")
    print(f"身份证号: {id_card if id_card else '(未提供，将使用AI提取)'}")
    print(f"交互模式: {'是' if interactive else '否（无效ID将直接放弃）'}")
    print(f"工作区: {WORK_ROOT}")
    print("=" * 60)
    
    # 步骤1：使用Qwen-VL提取数据
    print("\n[步骤1] 调用 Qwen-VL 提取检验指标...")
    data = extract_lab_metrics(image_path)
    
    if not data:
        print("[ERROR] 数据提取失败")
        return 1
    
    # 步骤2：强制校验身份证号（使用AI提取的ID作为备选）
    print("\n[步骤2] 验证身份证号...")
    extracted_id = data.get('patient_id')
    validated_id = validate_id_card(id_card, extracted_id, interactive=interactive)
    if not validated_id:
        print("[ERROR] 身份证号验证失败，终止处理")
        return 1
    id_card = validated_id
    print(f"[OK] 身份证号验证通过: {id_card}")
    
    # 步骤3：生成结构化文件
    print("\n[步骤3] 生成结构化报告文件...")
    saved_dir = save_structured_report(data, id_card)
    
    # 步骤4：显示结果摘要
    print("\n" + "=" * 60)
    print("提取完成！")
    print("=" * 60)
    print(f"保存位置: {saved_dir}")
    print(f"报告日期: {data.get('report_date')}")
    print(f"报告类型: {data.get('report_type')}")
    print(f"提取指标数: {len(data.get('metrics', {}))}")
    print("\n主要指标:")
    for key in ['WBC', 'RBC', 'HGB', 'PLT', 'CRP', 'hs-CRP']:
        if key in data.get('metrics', {}):
            info = data['metrics'][key]
            print(f"  {key}: {info.get('value')} {info.get('unit', '')}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
