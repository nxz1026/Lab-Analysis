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
import sys
import time
from pathlib import Path

from lab_analysis.llm_client import call_chat, parse_json_response, load_api_key
from lab_analysis.patient_id import encode, validate_id_card


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
    api_key = load_api_key("ZHIPU_API_KEY")
    image_b64 = encode_image_to_base64(image_path)
    model_name = "glm-4v-flash"

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

    max_retries = 3
    last_error = None
    for attempt in range(max_retries):
        if attempt > 0:
            wait_time = 2 ** attempt
            print(f"[Vision] 等待 {wait_time} 秒后重试...")
            time.sleep(wait_time)

        print(f"[Vision] 尝试使用模型: {model_name} (智谱AI) [尝试 {attempt + 1}/{max_retries}]")
        try:
            raw = call_chat(
                "zhipu",
                user_prompt=prompt,
                image_b64=image_b64,
                model=model_name,
                api_key=api_key,
            )
            result = parse_json_response(raw)
            result["model_used"] = model_name
            print(f"[Vision] [OK] 模型 {model_name} 调用成功")
            return result
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON解析失败: {e}")
            print(f"原始响应: {raw[:500]}")
            last_error = f"JSON解析失败: {e}"
            continue
        except Exception as e:
            print(f"[ERROR] 模型调用失败: {e}")
            if "429" in str(e):
                print("[WARNING] 遇到速率限制，将增加等待时间")
            last_error = str(e)
            continue

    print(f"[ERROR] 所有 {max_retries} 次尝试均失败。最后错误: {last_error}")
    return {
        "patient_id": None,
        "report_date": None,
        "report_type": None,
        "confidence": 0.0,
        "error": f"模型调用失败: {last_error}"
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
    print("[Vision] 调用 Qwen-VL API...")
    
    result = extract_info_from_image(image_path)
    
    # 强制校验身份证号（OCR 识别值作为 extracted_id 传入统一校验函数）
    raw_extracted = result.get('patient_id')
    if not raw_extracted:
        print("\n[WARNING] 未识别到身份证号")
    final_id = validate_id_card(raw_extracted, raw_extracted, interactive=args.interactive)
    if final_id:
        result['patient_id'] = final_id
        result['confidence'] = 1.0
    else:
        result['patient_id'] = None
        result['error'] = '身份证号校验未通过'
    
    # 输出结果
    print("\n" + "=" * 60)
    print("识别结果:")
    print("=" * 60)
    print(f"身份证号:   {result.get('patient_id', 'N/A')}")
    if result.get('patient_id'):
        print(f"脱敏ID:     {encode(result['patient_id'])}")
    print(f"报告日期:   {result.get('report_date', 'N/A')}")
    print(f"报告类型:   {result.get('report_type', 'N/A')}")
    print(f"置信度:     {result.get('confidence', 'N/A')}")
    if result.get('error'):
        print(f"错误信息:   {result['error']}")
    print("=" * 60)
    
    # 保存到文件
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # 添加脱敏ID字段
        output_result = result.copy()
        if result.get('patient_id'):
            output_result['patient_id_obf'] = encode(result['patient_id'])
        args.output.write_text(json.dumps(output_result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[OK] 结果已保存: {args.output}")
    
    # 输出JSON供后续脚本使用
    print("\nJSON输出:")
    # 添加脱敏ID字段
    json_result = result.copy()
    if result.get('patient_id'):
        json_result['patient_id_obf'] = encode(result['patient_id'])
    print(json.dumps(json_result, ensure_ascii=False, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
