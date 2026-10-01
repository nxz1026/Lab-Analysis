"""mcp_server.trend — render_quant_trend tool"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import mcp

# patient 目录名白名单: 脱敏 deid 是 base64url 串 (字母数字 + - _), 见
# lab_analysis/patient_id.encode; 真实 deid 长 58-62 字符, 故上界取 64
# (与 pipeline/cli.py 的 _DEID_RE 一致, 不能沿用 patient.py 的 {15,50} 上界).
_PATIENT_DIR_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _resolve_artifact_dir(out_dir: str, fallback: Path) -> Path:
    """把产物目录解析成绝对路径, 并强制其位于 WORK_ROOT 之内。

    out_dir 来自 LLM 调用方, 不加约束会变成任意目录创建 / 任意文件覆盖入口。
    """
    from lab_analysis.config import WORK_ROOT  # noqa: PLC0415

    target = Path(out_dir).resolve() if out_dir else fallback.resolve()
    root = WORK_ROOT.resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"out_dir 必须位于 WORK_ROOT 内: {target} 不在 {root} 下")
    return target


@mcp.tool()
def render_quant_trend(patient_id: str = "", out_dir: str = "", x_key: str = "std_ts") -> str:
    """把所有 quant_eval_report.json (1+ 个) 串成多 run trend PNG。

    Args:
        patient_id: 不传则全 patient 混排; 传则只取该 patient.
        out_dir: PNG 输出目录 (默认 = data/{patient_id or '_all'}/trend/).
        x_key: X 轴 label 来源 (std_ts / dspy_ts / deid).

    Returns:
        JSON 字符串:
        {
          "n_reports": int,
          "x_key": str,
          "png_path": str | None,
          "report_ids": [str, ...]
        }
    """
    try:
        from lab_analysis.quant_visualizer import render_trend_chart  # noqa: PLC0415
        from lab_analysis.utils import WORK_ROOT  # noqa: PLC0415

        base = WORK_ROOT / "data"
        reports: list[dict] = []
        report_ids: list[str] = []
        if base.is_dir():
            for pdir in sorted(base.iterdir()):
                if not pdir.is_dir() or not _PATIENT_DIR_RE.match(pdir.name):
                    continue
                if patient_id and pdir.name != patient_id:
                    continue
                for ts in sorted(pdir.iterdir()):
                    if not ts.is_dir():
                        continue
                    rj = ts / "04_reports" / "quant_eval_report.json"
                    if not rj.exists():
                        continue
                    try:
                        rep = json.loads(rj.read_text(encoding="utf-8"))
                        reports.append(rep)
                        report_ids.append(f"{pdir.name}/{ts.name}")
                    except (json.JSONDecodeError, OSError):
                        continue

        if not reports:
            return json.dumps(
                {
                    "n_reports": 0,
                    "x_key": x_key,
                    "png_path": None,
                    "report_ids": [],
                    "error": "no quant_eval_report.json found",
                },
                ensure_ascii=False,
                indent=2,
            )

        png_bytes = render_trend_chart(reports, x_key=x_key)
        out_base = _resolve_artifact_dir(out_dir, base / (patient_id or "_all") / "trend")
        out_base.mkdir(parents=True, exist_ok=True)
        png_path = out_base / "quant_eval_trend.png"
        png_path.write_bytes(png_bytes)
        return json.dumps(
            {
                "n_reports": len(reports),
                "x_key": x_key,
                "png_path": str(png_path),
                "report_ids": report_ids,
            },
            ensure_ascii=False,
            indent=2,
        )
    except Exception as e:
        return json.dumps(
            {"error": str(e), "type": type(e).__name__},
            ensure_ascii=False,
            indent=2,
        )
