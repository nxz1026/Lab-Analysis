#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vision_extractor.py — Vision 模块：从检验报告图片中提取患者ID、日期等信息

用法：
  python vision_extractor.py --image /path/to/image.jpg

输出：
  JSON 格式的患者ID、报告日期、报告类型等信息
"""
import argparse
import base64
import json
import re
import sys
from pathlib import Path

from .api_clients import call_zhipu_vision
from .config import ZHIPU_API_KEY


def validate_chinese_id(id_number: str) -> bool:
    """
    验证中国大陆身份证号格式
    - 18位数字（最后一位可能是X）
    - 或者15位数字（旧版）
    """
    if not id_number:
        return False
    
    # 18位身份证：17位数字 + 1位数字或X
    pattern_18 = r'^\d{17}[\dXx]$'
    # 15位身份证：15位数字
    pattern_15 = r'^\d{15}$'
    
    return bool(re.match(pattern_18, id_number) or re.match(pattern_15, id_number))


def get_api_key():
    """从统一配置获取 API Key"""
    if not ZHIPU_API_KEY:
        raise ValueError("未找到 ZHIPU_API_KEY，请配置在 .env 文件或环境变量中")
    return ZHIPU_API_KEY


def encode_image_to_base64(image_path: Path) -> str:
    """将图片编码为 base64（自动转为RGB并压缩）"""
    from PIL import Image
    from io import BytesIO
    img = Image.open(image_path).convert("RGB")
    # 压缩到宽2000以内，减少base64大小
    if max(img.size) > 2000:
        ratio = 2000 / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def extract_info_from_image(image_path: Path, use_free_model: bool = True) -> dict:
    """
    使用 Qwen-VL 从检验报告图片中提取关键信息

    参数：
        image_path: 图片路径
        use_free_model: 是否优先使用免费模型（默认True）

    返回：
    {
        "patient_id": "患者ID",
        "report_date": "报告日期 YYYY-MM-DD",
        "report_type": "outpatient/inpatient",
        "confidence": 置信度 0-1
    }
    """
    api_key = get_api_key()
    image_b64 = encode_image_to_base64(image_path)

    prompt = """你是医疗文档OCR专家。请从这张检验报告图片中提取以下关键信息：

1. 患者ID/诊疗卡号（通常是数字，可能在"诊疗卡号"、"病历号"、"患者ID"等字段后）
2. 报告日期（格式：YYYY-MM-DD 或 YYYY/MM/DD）
3. 报告类型：门诊(outpatient)还是住院(inpatient)

请以JSON格式返回，例如：
{
  "patient_id": "YOUR_PATIENT_ID",
  "report_date": "2026-03-24",
  "report_type": "outpatient",
  "confidence": 0.95
}

如果某个字段无法确定，请用 null 表示。
只返回JSON，不要其他文字。"""

    model_name = "glm-4v-flash"

    print(f"[Vision] 使用模型: {model_name} (智谱AI)")

    try:
        data = call_zhipu_vision(
            api_key=api_key,
            image_b64=image_b64,
            prompt=prompt,
            model=model_name,
            timeout=120,
        )
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return {
            "patient_id": None,
            "report_date": None,
            "report_type": None,
            "confidence": 0.0,
            "error": f"智谱AI调用失败（已重试5次）: {e}",
        }

    print(f"[Vision] [OK] 模型 {model_name} 调用成功")

    # 解析JSON响应
    try:
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        result = json.loads(content.strip())
        result['model_used'] = model_name
        return result
    except json.JSONDecodeError as e:
        return {
            "patient_id": None,
            "report_date": None,
            "report_type": None,
            "confidence": 0.0,
            "error": f"JSON解析失败: {e}",
        }


def main():
    parser = argparse.ArgumentParser(description="Vision模块：从检验报告图片提取患者信息")
    parser.add_argument("--image", "-i", required=True, type=Path, help="图片路径")
    parser.add_argument("--output", "-o", type=Path, help="输出JSON文件路径（可选）")
    parser.add_argument("--interactive", action="store_true", help="交互式确认模式")
    args = parser.parse_args()
    
    image_path = args.image
    if not image_path.exists():
        print(f"[ERROR] 文件不存在: {image_path}")
        return 1
    
    print(f"[Vision] 正在分析图片: {image_path.name}")
    print(f"[Vision] 调用 Qwen-VL API...")
    
    result = extract_info_from_image(image_path)
    
    # 验证患者ID是否为有效身份证号
    patient_id = result.get('patient_id')
    if not patient_id or (patient_id and not validate_chinese_id(patient_id)):
        if not patient_id:
            print(f"\n[WARNING] 未识别到患者ID")
        else:
            print(f"\n[WARNING] 识别到的患者ID '{patient_id}' 不是有效的身份证号格式")
        print(f"   期望格式: 18位数字(最后一位可能是X) 或 15位数字")
        
        if args.interactive:
            print(f"\n请选择操作:")
            print(f"  1. 手动输入正确的患者ID")
            print(f"  2. 放弃此数据")
            choice = input(f"\n请输入选择 (1/2): ").strip()
            
            if choice == '1':
                new_id = input("请输入患者身份证号: ").strip()
                if validate_chinese_id(new_id):
                    result['patient_id'] = new_id
                    result['confidence'] = 1.0
                    print(f"[OK] 已更新患者ID: {new_id}")
                else:
                    print(f"[ERROR] 输入的ID格式无效，放弃此数据")
                    result['patient_id'] = None
                    result['error'] = '用户输入的ID格式无效'
            elif choice == '2':
                print(f"[INFO] 用户选择放弃此数据")
                result['patient_id'] = None
                result['error'] = '用户放弃'
            else:
                print(f"[ERROR] 无效的选择，默认放弃此数据")
                result['patient_id'] = None
                result['error'] = '用户输入无效选项'
        else:
            # 非交互模式下，标记为无效
            result['patient_id'] = None
            result['error'] = f'识别的ID "{patient_id}" 不是有效的身份证号'
    
    # 输出结果
    print("\n" + "=" * 60)
    print("识别结果:")
    print("=" * 60)
    print(f"患者ID:     {result.get('patient_id', 'N/A')}")
    print(f"报告日期:   {result.get('report_date', 'N/A')}")
    print(f"报告类型:   {result.get('report_type', 'N/A')}")
    print(f"置信度:     {result.get('confidence', 'N/A')}")
    if result.get('error'):
        print(f"错误信息:   {result['error']}")
    print("=" * 60)
    
    # 保存到文件
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[OK] 结果已保存: {args.output}")
    
    # 输出JSON供后续脚本使用
    print("\nJSON输出:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
