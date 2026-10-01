"""extract_lab_data.ocr — 图片 base64 编码 + SCNet OCR API 调用。"""

from __future__ import annotations

import base64
import contextlib
import os
import tempfile
import time
from io import BytesIO
from pathlib import Path

import requests

from .. import _log

logger = _log.get_logger(__name__)

MAX_OCR_SIDE = 1600


def encode_image_to_base64(image_path: Path) -> str:
    """将图片编码为 base64（自动转为 RGB 并压缩）。"""
    from PIL import Image

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        if max(img.size) > MAX_OCR_SIDE:
            ratio = MAX_OCR_SIDE / max(img.size)
            # Pillow 10+ 把 LANCZOS 移到 Resampling 枚举，旧的 Image.LANCZOS 仍可用但 mypy stub 不再导出
            img = img.resize(  # type: ignore[attr-defined]
                (int(img.width * ratio), int(img.height * ratio)),
                Image.LANCZOS,  # type: ignore[attr-defined]
            )
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")


def _prepare_upload(image_path: Path) -> str:
    """长边超限时等比缩放到临时文件, 返回待上传路径。

    SCNet OCR 对超过 ~2000 px 的长边会返回 435 OCR Error, 故上传前先缩放。
    缩放时写临时文件; 调用方负责清理 (见 ``call_scnet_ocr`` 的 finally)。
    """
    from PIL import Image

    with Image.open(image_path) as raw:
        raw.load()
        w, h = raw.size
        if max(w, h) <= MAX_OCR_SIDE:
            return str(image_path)
        img = raw.convert("RGB")
        img.thumbnail((MAX_OCR_SIDE, MAX_OCR_SIDE))
        fd, tmp_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            img.save(tmp_path, "JPEG", quality=85)
        except (ValueError, TypeError, KeyError, AttributeError, OSError, RuntimeError):
            Path(tmp_path).unlink()
            raise
        return tmp_path


def _post_ocr(url: str, headers: dict, payload: dict, upload_path: str) -> "requests.Response":
    """带重试地 POST 图片到 SCNet OCR。仅对传输层异常重试, 最多 3 次。"""
    for attempt in range(3):
        try:
            with Path(upload_path).open("rb") as fh:
                files = [("file", (Path(upload_path).name, fh, "image/jpeg"))]
                return requests.post(url, headers=headers, data=payload, files=files, timeout=60)
        except requests.RequestException:
            if attempt < 2:
                time.sleep(1)
            else:
                raise


def _extract_text_lines(data: dict) -> list[str]:
    """从 SCNet 响应里按层取出非空文本行 (data -> result -> elements -> text)。"""
    lines: list[str] = []
    for item in data.get("data", []):
        for r in item.get("result", []):
            for el in r.get("elements", {}).get("text", []):
                t = el.get("text", "").strip()
                if t:
                    lines.append(t)
    return lines


def call_scnet_ocr(image_path: Path, api_key: str) -> str:
    """调用 SCNet OCR API 提取图片中的原始文本。

    SCNet OCR 对超过 ~2000 px 的长边会返回 435 OCR Error。
    上传前先按 ``MAX_OCR_SIDE`` 做等比缩放，长边 > MAX_OCR_SIDE 才处理。
    """
    url = "https://api.scnet.cn/api/llm/v1/ocr/recognize"
    payload = {"ocrType": "general"}
    headers = {"Authorization": f"Bearer {api_key}"}

    upload_path = _prepare_upload(image_path)
    try:
        resp = _post_ocr(url, headers, payload, upload_path)
    finally:
        if upload_path != str(image_path):
            with contextlib.suppress(OSError):
                Path(upload_path).unlink()

    resp.raise_for_status()
    return "\n".join(_extract_text_lines(resp.json()))
