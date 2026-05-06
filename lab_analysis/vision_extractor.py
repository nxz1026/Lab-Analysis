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
import os
import re
import sys
from pathlib import Path

import requests


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
    """从环境变量或配置文件获取 API Key"""
    # 尝试从环境变量获取
    api_key = os.environ.get("OPENROUTER_API_KEY")
    
    if not api_key:
        # 尝试从 .env 文件读取
        env_file = Path.home() / ".hermes" / ".env"
        if env_file.exists():
            content = env_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    
    if not api_key:
        raise ValueError("未找到 OPENROUTER_API_KEY，请配置在 ~/.hermes/.env 或环境变量中")
    
    return api_key


def encode_image_to_base64(image_path: Path) -> str:
    """将图片编码为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


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
  "patient_id": "513229198801040014",
  "report_date": "2026-03-24",
  "report_type": "outpatient",
  "confidence": 0.95
}

如果某个字段无法确定，请用 null 表示。
只返回JSON，不要其他文字。"""

    # 优先使用免费模型，如果失败则切换到付费模型
    if use_free_model:
        # OpenRouter 免费模型列表（按优先级）
        models_to_try = [
            "qwen/qwen-2.5-vl-72b-instruct",  # 免费且性能较好
            "qwen/qwen-vl-plus",               # 付费但更稳定
        ]
    else:
        models_to_try = ["qwen/qwen-vl-plus"]
    
    last_error = None
    
    for model_name in models_to_try:
        try:
            print(f"[Vision] 尝试使用模型: {model_name}")
            
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
                "max_tokens": 2000
            }
            
            # 使用 OpenRouter API
            api_url = "https://openrouter.ai/api/v1/chat/completions"
            
            resp = requests.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/nxz1026/Lab-Analysis",  # OpenRouter 要求
                    "X-Title": "Lab-Analysis Pipeline"
                },
                json=payload,
                timeout=120
            )
            resp.raise_for_status()
            
            data = resp.json()
            # OpenAI 兼容模式返回格式
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            print(f"[Vision] [OK] 模型 {model_name} 调用成功")
            
            # 解析JSON响应
            try:
                # 清理可能的markdown代码块标记
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                
                result = json.loads(content.strip())
                result['model_used'] = model_name  # 记录使用的模型
                return result
            except json.JSONDecodeError as e:
                print(f"[WARNING] JSON解析失败: {e}")
                print(f"原始响应: {content}")
                last_error = "JSON解析失败"
                continue  # 尝试下一个模型
        
        except Exception as e:
            print(f"[WARNING] 模型 {model_name} 调用失败: {e}")
            last_error = str(e)
            continue  # 尝试下一个模型
    
    # 所有模型都失败了
    print(f"❌ 所有模型都调用失败")
    return {
        "patient_id": None,
        "report_date": None,
        "report_type": None,
        "confidence": 0.0,
        "error": f"所有模型调用失败: {last_error}"
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
