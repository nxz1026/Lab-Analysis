#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_lab_data.py — 从检验报告图片中提取完整检验指标并生成结构化文件

用法：
  python extract_lab_data.py --image /path/to/lab_report.jpg --id-card <身份证号>

功能：
  1. 使用 SCNet OCR + DeepSeek 从检验报告图片中提取所有检验指标
  2. 生成 metadata.md（报告元信息）
  3. 生成 metrics.md（检验指标数据，YAML格式）
  4. 保存到 raw/patient_{ID}/papers/lab_report_{date}_{type}/ 目录
"""

import argparse
import base64
import contextlib
import os
import re
import sys
import tempfile
from pathlib import Path

import requests

from lab_analysis.llm_client import load_api_key
from lab_analysis.patient_id import validate_id_card

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


# SCNet OCR 对超过 ~2000 px 的长边会返回 435 OCR Error。
# 上传前先按 ``MAX_OCR_SIDE`` 做等比缩放，长边 > MAX_OCR_SIDE 才处理。
MAX_OCR_SIDE = 1600


def call_scnet_ocr(image_path: Path, api_key: str) -> str:
    """调用 SCNet OCR API 提取图片中的原始文本。

    SCNet OCR 对超过 ~2000 px 的长边会返回 435 OCR Error。
    上传前先按 ``MAX_OCR_SIDE`` 做等比缩放，长边 > MAX_OCR_SIDE 才处理。
    """
    url = "https://api.scnet.cn/api/llm/v1/ocr/recognize"
    from PIL import Image

    with Image.open(image_path) as raw:
        raw.load()
        w, h = raw.size
        if max(w, h) > MAX_OCR_SIDE:
            img = raw.convert("RGB")
            img.thumbnail((MAX_OCR_SIDE, MAX_OCR_SIDE))
            fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
            os.close(fd)
            try:
                img.save(tmp_path, "JPEG", quality=85)
                upload_path = tmp_path
            except Exception:
                os.unlink(tmp_path)
                raise
        else:
            upload_path = str(image_path)

    try:
        with open(upload_path, "rb") as fh:
            files = [("file", (Path(upload_path).name, fh, "image/jpeg"))]
            payload = {"ocrType": "general"}
            headers = {"Authorization": f"Bearer {api_key}"}
            resp = requests.post(url, headers=headers, data=payload, files=files, timeout=60)
    finally:
        if upload_path != str(image_path):
            with contextlib.suppress(OSError):
                os.unlink(upload_path)
    resp.raise_for_status()
    data = resp.json()

    lines = []
    for item in data.get("data", []):
        for r in item.get("result", []):
            for el in r.get("elements", {}).get("text", []):
                t = el.get("text", "").strip()
                if t:
                    lines.append(t)
    return "\n".join(lines)


# ── OCR 文本解析（正则，不依赖 LLM）────────────────────────────────

_METRIC_ALIAS = {
    "白细胞计数": "WBC",
    "WBC": "WBC",
    "红细胞计数": "RBC",
    "RBC": "RBC",
    "血红蛋白测定": "HGB",
    "HGB": "HGB",
    "红细胞压积": "HCT",
    "HCT": "HCT",
    "血小板计数": "PLT",
    "PLT": "PLT",
    "血小板比容": "PCT",
    "PCT": "PCT",
    "大型血小板比率": "P-LCR",
    "P-LCR": "P-LCR",
    "平均红细胞体积": "MCV",
    "MCV": "MCV",
    "平均红细胞血红蛋白含量": "MCH",
    "MCH": "MCH",
    "平均红细胞血红蛋白浓度": "MCHC",
    "MCHC": "MCHC",
    "中性粒细胞百分率": "NEUT%",
    "NEUT%": "NEUT%",
    "淋巴细胞百分率": "LYMPH%",
    "LYMPH%": "LYMPH%",
    "单核细胞百分率": "MONO%",
    "MONO%": "MONO%",
    "嗜酸性粒细胞百分率": "EO%",
    "EO%": "EO%",
    "嗜碱性粒细胞百分率": "BASO%",
    "BASO%": "BASO%",
    "中性粒细胞绝对数": "NEUT#",
    "NEUT#": "NEUT#",
    "淋巴细胞绝对数": "LYMPH#",
    "LYMPH#": "LYMPH#",
    "单核细胞绝对数": "MONO#",
    "MONO#": "MONO#",
    "嗜酸性粒细胞绝对数": "EO#",
    "EO#": "EO#",
    "嗜碱性粒细胞绝对数": "BASO#",
    "BASO#": "BASO#",
    "红细胞体积分布宽度.*?SD": "RDW-SD",
    "RDW-SD": "RDW-SD",
    "红细胞变异系数.*?CV": "RDW-CV",
    "RDW-CV": "RDW-CV",
    "平均血小板体积": "MPV",
    "MPV": "MPV",
    "血小板体积分布宽度": "PDW",
    "PDW": "PDW",
    "C反应蛋白测定": "CRP",
    "CRP": "CRP",
    "超敏C反应蛋白": "hs-CRP",
    "hs-CRP": "hs-CRP",
}

_DATE_PATTERN = re.compile(r"(\d{4})\s*[-年]\s*(\d{1,2})\s*[-月]\s*(\d{1,2})")
_NAME_PATTERN = re.compile(r"姓名\(Name\).*?[:：]\s*(\S+)")
_ID_PATTERN = re.compile(r"诊疗卡号.*?(\d{17}[\dXx])")
# OCR 在标签后常写 \u201c.\u201d\u2014\u2014\u201c科别(Dept.)\u201d / \u201c诊断(Diag.)\u201d，括号后的点可选
# OCR 在标签后常带“.” (科别(Dept.) / 诊断(Diag.))，这个点可选。
_DEPT_PATTERN = re.compile(r"科别\(Dept\.?\)" r".*?[:：]\s*(\S+)")
_DIAG_PATTERN = re.compile(r"诊断\(Diag\.?\)" r".*?[:：]\s*(\S+)")


def _parse_value(raw_val: str) -> float:
    """解析数值：<10 → 10.0, >3.0 → 3.0, 6.70 → 6.70"""
    s = raw_val.strip().replace(" ", "")
    lt = re.match(r"<\s*([\d.]+)", s)
    if lt:
        return float(lt.group(1))
    gt = re.match(r">\s*([\d.]+)", s)
    if gt:
        return float(gt.group(1))
    return float(s)


def _parse_ocr_to_json(ocr_text: str) -> dict:
    """
    将 OCR 原始文本解析为结构化 JSON。

    OCR返回的表格格式（每字段单独一行）：
      序号
      项目名称(Test)      ← 如 "白细胞计数(WBC)"
      结果(Result)         ← 如 "6. 70"（可能含空格）
      单位(Unit)           ← 如 "10^9/L"
      参考范围(Ref.)       ← 如 "3. 5-9. 5"
    """
    result = {}

    # ── 患者信息 ──
    name_m = _NAME_PATTERN.search(ocr_text)
    id_m = _ID_PATTERN.search(ocr_text)
    dept_m = _DEPT_PATTERN.search(ocr_text)
    diag_m = _DIAG_PATTERN.search(ocr_text)
    date_m = _DATE_PATTERN.search(ocr_text)

    result["patient_id"] = id_m.group(1) if id_m else (name_m.group(1) if name_m else "")
    result["report_date"] = (
        f"{date_m.group(1)}-{date_m.group(2).zfill(2)}-{date_m.group(3).zfill(2)}" if date_m else ""
    )
    result["report_type"] = "outpatient"
    result["department"] = dept_m.group(1) if dept_m else ""
    result["physician"] = ""
    result["diagnosis"] = diag_m.group(1) if diag_m else ""

    # ── 指标解析（表格格式：序号行 → 名称行 → 数值行 → 单位行 → 参考范围行）──
    lines = [l.strip() for l in ocr_text.split("\n")]
    metrics = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        # 找到序号行（纯数字 或 "数字 *"）
        parts = line.split()
        if not parts or not parts[0].isdigit():
            i += 1
            continue
        # 下一行应该是指标名称
        if i + 1 >= len(lines):
            break
        name_line = lines[i + 1]
        # 再下一行应该是数值
        if i + 2 >= len(lines):
            break
        val_line = lines[i + 2]

        # 跳过表头行
        if name_line in ("项目名称(Test)", ""):
            i += 3
            continue

        # 优先从括号中提取缩写匹配，避免 "MCH" 误匹配 "MCHC"
        abbrev_m = re.search(r"\((\S+?)\)", name_line)
        matched_key = None
        if abbrev_m:
            abbrev = abbrev_m.group(1)
            matched_key = _METRIC_ALIAS.get(abbrev)
        if not matched_key:
            for pattern, key in _METRIC_ALIAS.items():
                if re.search(pattern, name_line):
                    matched_key = key
                    break

        if matched_key and val_line:
            with contextlib.suppress(ValueError):
                metrics[matched_key] = _parse_value(val_line)

        i += 3  # 跳过序号+名称+数值三行（单位/参考范围行不需要）

    result["metrics"] = metrics
    return result


def extract_lab_metrics(image_path: Path) -> dict:
    """
    [SCNet OCR + 正则解析] 从检验报告图片中提取完整检验指标数据

    流程：
      1. 调用 SCNet OCR API 提取图片原始文本
      2. 正则表达式直接解析为结构化 JSON（无需 LLM）

    返回：
    {
        "patient_id": "患者ID",
        "report_date": "YYYY-MM-DD",
        "report_type": "outpatient/inpatient",
        "department": "科室",
        "physician": "医生",
        "diagnosis": "诊断",
        "metrics": {
            "WBC": 7.5, "RBC": 4.8, ...
        }
    }
    """
    ocr_api_key = load_api_key("SCNET_OCR_API_KEY")
    print("[OCR] 调用 SCNet OCR 提取图片文字...")
    ocr_text = call_scnet_ocr(image_path, ocr_api_key)
    print(f"[OCR] 成功提取 {len(ocr_text)} 字符文本")

    print("[PARSE] 正则解析 OCR 文本...")
    result = _parse_ocr_to_json(ocr_text)
    n = len(result.get("metrics", {}))
    print(f"[OK] 成功提取 {n} 个检验指标 (SCNet OCR + 正则解析)")
    return result


def generate_metadata_md(data: dict, validated_patient_id: str) -> str:
    """
    生成 metadata.md 文件内容

    Args:
        data: AI提取的数据
        validated_patient_id: 用户验证过的患者ID（优先使用）
    """
    # 优先使用用户验证过的ID，如果为空则使用AI提取的ID
    patient_id = validated_patient_id if validated_patient_id else data.get("patient_id", "")

    md = f"""| 字段 | 值 |
|------|-----|
| 身份证号 | {patient_id} |
| 报告日期 | {data.get("report_date", "")} |
| 报告类型 | {data.get("report_type", "")} |
| 科室 | {data.get("department", "")} |
| 医生 | {data.get("physician", "")} |
| 诊断 | {data.get("diagnosis", "")} |
"""
    return md


def _sanitize_metrics(metrics: dict) -> dict:
    """清洗指标值，将 <X / >X 等非数字格式转为纯数字。

    处理规则：
    - "<10" → 10.0（取检测限值）
    - ">3.0" → 3.0（取检测限值）
    - "—" / "-" / "" → 删除该指标
    - 已为正确保留不变
    """
    cleaned = {}
    for key, val in metrics.items():
        if isinstance(val, (int, float)):
            cleaned[key] = float(val)
        elif isinstance(val, str):
            s = val.strip()
            if not s or s in ("—", "–", "-"):
                continue
            num_match = re.search(r"([0-9]+\.?\d*)", s)
            if num_match:
                cleaned[key] = float(num_match.group(1))
        elif isinstance(val, dict):
            inner = _sanitize_metrics(val)
            if inner:
                cleaned[key] = inner
    return cleaned


def generate_metrics_md(data: dict) -> str:
    """生成 metrics.md 文件内容（YAML格式）"""
    metrics = data.get("metrics", {})

    yaml_lines = []
    for key, val in metrics.items():
        if isinstance(val, (int, float)):
            yaml_lines.append(f"{key}: {val}")
        elif isinstance(val, dict):
            v = val.get("value")
            if v is not None:
                yaml_lines.append(f"{key}: {v}")

    return "\n".join(yaml_lines) + "\n"


def save_structured_report(data: dict, patient_id: str) -> str:
    """
    保存结构化报告到 papers/lab_report_{date}_{type}/ 目录

    返回：保存的目录路径
    """
    # 使用 pipeline 统一的 get_deid() 确保与后续步骤一致
    from lab_analysis.pipeline.cli import get_deid

    patient_id_obf = get_deid(patient_id)

    report_date = data.get("report_date", "").replace("-", "")
    report_type = data.get("report_type", "unknown")

    # 创建目录：papers/lab_report_YYYYMMDD_type/
    report_dir = (
        WORK_ROOT
        / "raw"
        / f"patient_{patient_id_obf}"
        / "papers"
        / f"lab_report_{report_date}_{report_type}"
    )
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
                if img_file.suffix.lower() in [".jpg", ".jpeg", ".png"]:
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
        # 步骤1：SCNet OCR + DeepSeek 提取数据
        print("\n[步骤1] SCNet OCR + DeepSeek 提取检验指标...")
        data = extract_lab_metrics(image_path)

        if not data:
            print("[ERROR] 数据提取失败")
            return False

        # 步骤1b：清洗指标值（处理 <10、>3.0 等非数字格式）
        if "metrics" in data:
            data["metrics"] = _sanitize_metrics(data["metrics"])
            print(f"[OK] 指标清洗完成: {len(data['metrics'])} 个有效指标")

        # 步骤2：强制校验身份证号（使用AI提取的ID作为备选）
        print("\n[步骤2] 验证身份证号...")
        extracted_id = data.get("patient_id")
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
        for key in ["WBC", "RBC", "HGB", "PLT", "CRP", "hs-CRP"]:
            if key in data.get("metrics", {}):
                val = data["metrics"][key]
                print(f"  {key}: {val}")
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
    parser.add_argument(
        "--id-card",
        type=str,
        default="",
        help="患者身份证号(18位或15位，可选，不提供则使用AI提取的ID)",
    )
    parser.add_argument(
        "--no-interactive", action="store_true", help="禁用交互模式（当身份证号无效时直接放弃数据）"
    )
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

    # 步骤1：SCNet OCR + DeepSeek 提取数据
    print("\n[步骤1] SCNet OCR + DeepSeek 提取检验指标...")
    data = extract_lab_metrics(image_path)

    if not data:
        print("[ERROR] 数据提取失败")
        return 1

    # 步骤2：强制校验身份证号（使用AI提取的ID作为备选）
    print("\n[步骤2] 验证身份证号...")
    extracted_id = data.get("patient_id")
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
    for key in ["WBC", "RBC", "HGB", "PLT", "CRP", "hs-CRP"]:
        if key in data.get("metrics", {}):
            info = data["metrics"][key]
            print(f"  {key}: {info.get('value')} {info.get('unit', '')}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
