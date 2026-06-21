"""对比 3 次 Pipeline 运行的产物，确认 compiled 模型生效"""
import json
from pathlib import Path

runs = {
    "182920_标准模式": r"e:\2026Workplace\Code\Lab-Analysis\data\846552421134373347\20260612_182920",
    "183621_DSPy未编译": r"e:\2026Workplace\Code\Lab-Analysis\data\846552421134373347\20260612_183621",
    "185152_DSPy已编译": r"e:\2026Workplace\Code\Lab-Analysis\data\846552421134373347\20260612_185152",
}

for name, root in runs.items():
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    root = Path(root)

    # 文献解读
    interp_json = root / "03_literature" / "literature_interpretation.json"
    if interp_json.exists():
        with open(interp_json, encoding='utf-8') as f:
            data = json.load(f)
        conf = data.get('confidence', '?')
        mode = data.get('mode', 'standard')
        print(f"  [⑥] literature_interpreter: mode={mode}, confidence={conf}")

    # MRI
    mri_files = [
        root / "03_literature" / "mri_report_check_results.json",
        root / "03_literature" / "mri_analysis_results.json"
    ]
    for mf in mri_files:
        if mf.exists():
            with open(mf, encoding='utf-8') as f:
                data = json.load(f)
            mode = data.get('mode', 'standard')
            n = data.get('analyzed_count', len(data.get('results', [])))
            conf = data.get('results', [{}])[0].get('confidence', '?') if data.get('results') else '?'
            print(f"  [⑦] {mf.name}: mode={mode}, n={n}, conf={conf}")

    # 最终报告
    final_md = root / "04_reports" / "final_integrated_report.md"
    if final_md.exists():
        content = final_md.read_text(encoding='utf-8')
        n_lines = content.count('\n')
        n_sections = content.count('## ')
        print(f"  [⑧] final_report: {n_lines} 行, {n_sections} 章节")

    # DSPy prompts
    dspy_dir = root / "03_literature" / "dspy_prompts"
    if dspy_dir.exists():
        n = len(list(dspy_dir.glob('*')))
        print(f"  dspy_prompts/03: {n} 文件")
    dspy_dir2 = root / "04_reports" / "dspy_prompts"
    if dspy_dir2.exists():
        n = len(list(dspy_dir2.glob('*')))
        print(f"  dspy_prompts/04: {n} 文件")
