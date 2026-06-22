"""gen_final_report_pdf.py — 将最终综合报告 Markdown 转为 PDF

依赖（可选）: weasyprint + markdown
安装: pip install "lab-analysis[pdf]"

用法:
    python -m lab_analysis.gen_final_report_pdf \\
        --md 04_reports/final_integrated_report.md \\
        --img-dir 02_analyzed/figures \\
        --out 04_reports/final_integrated_report.pdf
"""

from __future__ import annotations

from pathlib import Path

# ── 依赖可用性检测 ──────────────────────────────────────────────────
try:
    import markdown

    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False

try:
    import weasyprint

    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

HAS_PDF_DEPS = HAS_MARKDOWN and HAS_WEASYPRINT


# ── CSS 样式（中文友好 + 医疗报告风格） ─────────────────────────────

_PDF_CSS = """
@page {
    size: A4;
    margin: 2.5cm 2cm 2.5cm 2cm;
    @bottom-center {
        content: counter(page) " / " counter(pages);
        font-size: 9pt;
        color: #666;
    }
}
body {
    font-family: "Microsoft YaHei", "SimSun", "Noto Sans CJK SC",
                 "WenQuanYi Micro Hei", sans-serif;
    font-size: 11pt;
    line-height: 1.7;
    color: #222;
}
h1 { font-size: 18pt; color: #1a5276; border-bottom: 2px solid #2980b9; padding-bottom: 4pt; }
h2 { font-size: 14pt; color: #2c3e50; margin-top: 20pt; }
h3 { font-size: 12pt; color: #34495e; }
strong { color: #000; }
table { border-collapse: collapse; width: 100%; margin: 10pt 0; }
th, td { border: 1px solid #ccc; padding: 6pt 8pt; text-align: left; }
th { background-color: #ecf0f1; font-weight: bold; }
img { max-width: 100%; height: auto; margin: 10pt 0; }
code { font-family: "Consolas", "Courier New", monospace; font-size: 10pt; }
blockquote { border-left: 3px solid #2980b9; padding-left: 10pt; color: #555; margin: 10pt 0; }
"""


def md_to_pdf(
    md_path: str | Path,
    output_path: str | Path,
    img_dir: str | Path | None = None,
) -> bool:
    """将 Markdown 报告文件转换为 PDF。

    Args:
        md_path: 输入的 .md 文件路径。
        output_path: 输出的 .pdf 文件路径。
        img_dir: 图片目录路径。MD 中相对路径的图片会从该目录查找。

    Returns:
        True 转换成功；False 因依赖缺失跳过。
    """
    if not HAS_PDF_DEPS:
        missing = []
        if not HAS_MARKDOWN:
            missing.append("markdown")
        if not HAS_WEASYPRINT:
            missing.append("weasyprint")
        print(f"  [SKIP] PDF 生成需要可选依赖: pip install {' '.join(missing)}")
        return False

    md_path = Path(md_path)
    output_path = Path(output_path)
    if img_dir:
        img_dir = Path(img_dir)

    if not md_path.exists():
        print(f"  [WARNING] Markdown 文件不存在: {md_path}")
        return False

    print(f"  [PDF] 转换: {md_path.name} → {output_path.name}")

    # 1. 读取 MD
    md_text = md_path.read_text(encoding="utf-8")

    # 2. 修正图片路径（相对 → 绝对）
    if img_dir:
        import re

        def _fix_img_path(match):
            src = match.group(1)
            if not src.startswith(("http://", "https://", "/")):
                abs_src = (img_dir / src).resolve()
                if abs_src.exists():
                    return f'<img src="file:///{abs_src.as_posix()}" />'
            return match.group(0)

        md_text = re.sub(r'<img\s+src="([^"]+)"\s*/>', _fix_img_path, md_text)
        md_text = re.sub(
            r"!\[([^\]]*)\]\(([^)]+)\)",
            lambda m: (
                f'<img src="{_fix_img_path_wrapper(m, img_dir)}" alt="{m.group(1)}" />'
                if _fix_img_path_wrapper(m, img_dir)
                else m.group(0)
            ),
            md_text,
        )

    # 3. MD → HTML
    html_body = markdown.markdown(
        md_text,
        extensions=["extra", "tables", "fenced_code"],
    )

    # 4. 包装为完整 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>{_PDF_CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    # 5. HTML → PDF
    output_path.parent.mkdir(parents=True, exist_ok=True)
    weasyprint.HTML(string=html).write_pdf(str(output_path))
    print(f"  [OK] PDF 已保存: {output_path}")
    return True


def _fix_img_path_wrapper(match, img_dir):
    """辅助：修正 Markdown 图片路径。"""
    src = match.group(2)
    if not src.startswith(("http://", "https://", "/")):
        abs_src = (img_dir / src).resolve()
        if abs_src.exists():
            return f"file:///{abs_src.as_posix()}"
    return src


def main():
    import argparse

    parser = argparse.ArgumentParser(description="最终报告 Markdown → PDF 转换")
    parser.add_argument("--md", required=True, help="输入的 .md 文件路径")
    parser.add_argument("--img-dir", default=None, help="图片目录路径（可选）")
    parser.add_argument("--out", required=True, help="输出的 .pdf 文件路径")
    args = parser.parse_args()

    md_to_pdf(args.md, args.out, args.img_dir)


if __name__ == "__main__":
    main()
