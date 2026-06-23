"""extract_lab_data.parser — OCR 文本 → 结构化 JSON 解析。"""

from __future__ import annotations

import contextlib
import re
from pathlib import Path

from lab_analysis.llm_client import load_api_key

from .. import _log
from . import ocr as _ocr

logger = _log.get_logger(__name__)

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
_DEPT_PATTERN = re.compile(r"科别\(Dept\.?\).*?[:：]\s*(\S+)")
_DIAG_PATTERN = re.compile(r"诊断\(Diag\.?\).*?[:：]\s*(\S+)")


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
    """将 OCR 原始文本解析为结构化 JSON。

    OCR 返回的表格格式（每字段单独一行）：
      序号
      项目名称(Test)      ← 如 "白细胞计数(WBC)"
      结果(Result)         ← 如 "6. 70"（可能含空格）
      单位(Unit)           ← 如 "10^9/L"
      参考范围(Ref.)       ← 如 "3. 5-9. 5"
    """
    result: dict = {}
    name_m = _NAME_PATTERN.search(ocr_text)
    id_m = _ID_PATTERN.search(ocr_text)
    dept_m = _DEPT_PATTERN.search(ocr_text)
    diag_m = _DIAG_PATTERN.search(ocr_text)
    date_m = _DATE_PATTERN.search(ocr_text)
    result["patient_id"] = id_m.group(1) if id_m else name_m.group(1) if name_m else ""
    result["report_date"] = (
        f"{date_m.group(1)}-{date_m.group(2).zfill(2)}-{date_m.group(3).zfill(2)}" if date_m else ""
    )
    result["report_type"] = "outpatient"
    result["department"] = dept_m.group(1) if dept_m else ""
    result["physician"] = ""
    result["diagnosis"] = diag_m.group(1) if diag_m else ""
    lines = [l.strip() for l in ocr_text.split("\n")]
    metrics: dict = {}
    i = 0
    while i < len(lines):
        line = lines[i]
        parts = line.split()
        if not parts or not parts[0].isdigit():
            i += 1
            continue
        if i + 1 >= len(lines):
            break
        name_line = lines[i + 1]
        if i + 2 >= len(lines):
            break
        val_line = lines[i + 2]
        if name_line in ("项目名称(Test)", ""):
            i += 3
            continue
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
        i += 3
    result["metrics"] = metrics
    return result


def extract_lab_metrics(image_path: Path) -> dict:
    """[SCNet OCR + 正则解析] 从检验报告图片中提取完整检验指标数据。

    流程：
      1. 调用 SCNet OCR API 提取图片原始文本
      2. 正则表达式直接解析为结构化 JSON（无需 LLM）
    """
    ocr_api_key = load_api_key("SCNET_OCR_API_KEY")
    logger.info("[OCR] 调用 SCNet OCR 提取图片文字...")
    ocr_text = _ocr.call_scnet_ocr(image_path, ocr_api_key)
    logger.info(f"[OCR] 成功提取 {len(ocr_text)} 字符文本")
    logger.info("[PARSE] 正则解析 OCR 文本...")
    result = _parse_ocr_to_json(ocr_text)
    n = len(result.get("metrics", {}))
    logger.info(f"[OK] 成功提取 {n} 个检验指标 (SCNet OCR + 正则解析)")
    return result
