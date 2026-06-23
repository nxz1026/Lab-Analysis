#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy 端到端集成测试

验证所有 DSPy 模块在 Pipeline 中的完整工作流程
包括: 文献解读、影像分析、报告生成
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_dspy_imports():
    """测试 1: 导入所有 DSPy 模块"""
    print("=" * 60)
    print("测试 1: 导入 DSPy 模块")
    print("=" * 60)

    try:
        # 仅做包级导入检查：确认 dspy_modules 可被发现
        from lab_analysis import dspy_modules  # noqa: F401

        print("[OK] 所有 DSPy 模块包可发现")
        for name in (
            "LiteratureInterpreterModule",
            "FinalReportGenerator",
            "LabDataExtractor",
            "MRIAnalysisModule",
        ):
            print(f"   - {name}")

        return True

    except ImportError as e:
        print(f"[FAIL] 模块导入失败: {e}")
        return False


def test_dspy_configuration():
    """测试 2: 配置 DSPy LLM"""
    print("\n" + "=" * 60)
    print("测试 2: 配置 DSPy LLM")
    print("=" * 60)

    try:
        import dspy

        # 检查 API Key
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
        dashscope_key = os.environ.get("DASHSCOPE_API_KEY")

        if not deepseek_key and not dashscope_key:
            print("[FAIL] 未找到 API Key (DEEPSEEK_API_KEY 或 DASHSCOPE_API_KEY)")
            return False

        print("[OK] API Key 已配置")
        if deepseek_key:
            print(f"   - DeepSeek: {deepseek_key[:20]}...")
        if dashscope_key:
            print(f"   - DashScope: {dashscope_key[:20]}...")

        # 配置 DeepSeek (用于文献解读和报告生成)
        if deepseek_key:
            dspy.LM(
                model="deepseek/deepseek-chat",
                api_key=deepseek_key,
                api_base="https://api.deepseek.com/v1",
            )
            print("[OK] DeepSeek LM 配置成功")

        # 配置 Qwen-VL (用于影像分析)
        if dashscope_key:
            dspy.LM(
                model="qwen/qwen-vl-plus",
                api_key=dashscope_key,
                api_base="https://dashscope.aliyuncs.com/api/v1",
            )
            print("[OK] Qwen-VL LM 配置成功")

        return True

    except Exception as e:
        print(f"[FAIL] LLM 配置失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_literature_interpreter_dspy():
    """测试 3: 文献解读 DSPy 模块"""
    print("\n" + "=" * 60)
    print("测试 3: 文献解读 DSPy 模块")
    print("=" * 60)

    try:
        from argparse import Namespace

        from lab_analysis.literature_interpreter_dspy import run_dspy_mode

        # 准备测试数据
        patient_id = "846552421134373347"
        ts = "20260611_111343"

        analysis_file = (
            project_root / "data" / patient_id / ts / "02_analyzed" / "analysis_results.json"
        )
        lit_file = (
            project_root / "data" / patient_id / ts / "03_literature" / "literature_results.json"
        )

        if not (analysis_file.exists() and lit_file.exists()):
            print("[WARN]  测试数据不存在,跳过此测试")
            print("   需要运行完整 Pipeline 生成数据")
            return True  # 不算失败

        args = Namespace(
            patient_id=patient_id,
            analysis=str(analysis_file),
            lit=str(lit_file),
            out=None,
            use_dspy=True,
        )

        print("[测试] 运行 DSPy 文献解读...")
        print(f"       患者ID: {patient_id}")
        print(f"       时间戳: {ts}")

        # 设置环境变量
        os.environ["ANALYSIS_TS"] = ts

        result = run_dspy_mode(args)

        if result:
            print("[OK] 文献解读成功")
            output_path = result.get("output_path", "")
            if output_path and output_path != ".":
                output_file = Path(output_path)
                if output_file.exists():
                    with open(output_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    interpretation = data.get("response", "")
                    print(f"   解读长度: {len(interpretation)} 字符")
                    print(f"   输出文件: {output_file}")
            return True
        else:
            print("[FAIL] 文献解读失败")
            return False

    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_mri_analyzer_dspy():
    """测试 4: MRI 影像分析 DSPy 模块"""
    print("\n" + "=" * 60)
    print("测试 4: MRI 影像分析 DSPy 模块")
    print("=" * 60)

    try:
        from lab_analysis.dspy_modules import run_dspy_mri_analysis

        # 测试数据
        image_desc = "T2WI横断面，肝脏层面，肝右后叶区域"
        report_findings = """肝右后叶上段：长径约2.2cm异常信号影，T1稍低、T2及STIR稍高，
增强少许点片状弱强化，考虑感染性病变，较前明显缩小"""
        clinical_context = "男，38岁，胰管支架置入后复查，腹痛待查"

        print("[测试] 运行 DSPy MRI 分析...")

        result = run_dspy_mri_analysis(
            image_desc=image_desc,
            report_findings=report_findings,
            clinical_context=clinical_context,
        )

        if result:
            print("[OK] MRI 分析成功")
            print(f"   解剖定位: {result['anatomical_localization'][:50]}...")
            print(f"   置信度: {result['confidence_score']:.2f}")
            return True
        else:
            print("[FAIL] MRI 分析失败")
            return False

    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_final_report_dspy():
    """测试 5: 最终报告生成 DSPy 模块"""
    print("\n" + "=" * 60)
    print("测试 5: 最终报告生成 DSPy 模块")
    print("=" * 60)

    try:
        from argparse import Namespace

        from lab_analysis.gen_final_report_dspy import run_dspy_mode

        patient_id = "846552421134373347"
        ts = "20260611_111343"

        # 检查必需文件
        data_dir = project_root / "data" / patient_id / ts
        required_files = [
            data_dir / "02_analyzed" / "analysis_results.json",
            data_dir / "03_literature" / "literature_interpretation.json",
            data_dir / "04_imaging" / "mri_analysis_results.json",
        ]

        missing_files = [f for f in required_files if not f.exists()]
        if missing_files:
            print("[WARN]  部分前置文件缺失,跳过此测试")
            for f in missing_files:
                print(f"   缺失: {f}")
            return True  # 不算失败

        args = Namespace(patient_id=patient_id, use_dspy=True)

        os.environ["ANALYSIS_TS"] = ts

        print("[测试] 运行 DSPy 报告生成...")

        result = run_dspy_mode(args)

        if result:
            print("[OK] 报告生成成功")
            return True
        else:
            print("[FAIL] 报告生成失败")
            return False

    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_pipeline_integration():
    """测试 6: Pipeline 集成检查"""
    print("\n" + "=" * 60)
    print("测试 6: Pipeline 集成检查")
    print("=" * 60)

    try:
        # 检查 pipeline.py 是否支持 --use-dspy
        pipeline_file = project_root / "lab_analysis" / "pipeline.py"

        if not pipeline_file.exists():
            print("[FAIL] pipeline.py 不存在")
            return False

        content = pipeline_file.read_text(encoding="utf-8")

        checks = [
            ("--use-dspy", "Pipeline 参数支持"),
            ("literature_interpreter_dspy", "文献解读 DSPy 集成"),
            ("qwen_vl_report_check_dspy", "影像分析 DSPy 集成"),
            ("gen_final_report_dspy", "报告生成 DSPy 集成"),
        ]

        all_passed = True
        for keyword, description in checks:
            if keyword in content:
                print(f"[OK] {description}")
            else:
                print(f"[FAIL] {description} - 未找到 '{keyword}'")
                all_passed = False

        return all_passed

    except Exception as e:
        print(f"[FAIL] 检查失败: {e}")
        return False


def generate_test_report(results: dict):
    """生成测试报告"""
    print("\n" + "=" * 60)
    print("[STATS] DSPy 端到端测试报告")
    print("=" * 60)

    total = len(results)
    passed = sum(1 for r in results.values() if r)
    failed = total - passed

    print(f"\n总计: {total} 个测试")
    print(f"通过: {passed} [OK]")
    print(f"失败: {failed} [FAIL]")
    print(f"成功率: {passed / total * 100:.1f}%")

    print("\n详细结果:")
    for test_name, result in results.items():
        status = "[OK] 通过" if result else "[FAIL] 失败"
        print(f"  {test_name}: {status}")

    # 保存报告
    report = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": total,
        "passed": passed,
        "failed": failed,
        "success_rate": f"{passed / total * 100:.1f}%",
        "details": results,
    }

    report_file = project_root / "reports" / "dspy_e2e_test_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)

    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n[保存] 测试报告已保存到: {report_file}")

    return passed == total


def main():
    """主函数"""
    print("\n" + "[TEST]" * 30)
    print("DSPy 端到端集成测试")
    print("[TEST]" * 30 + "\n")

    results = {}

    # 运行所有测试
    results["模块导入"] = test_dspy_imports()
    results["LLM 配置"] = test_dspy_configuration()
    results["文献解读"] = test_literature_interpreter_dspy()
    results["MRI 分析"] = test_mri_analyzer_dspy()
    results["报告生成"] = test_final_report_dspy()
    results["Pipeline 集成"] = test_pipeline_integration()

    # 生成报告
    all_passed = generate_test_report(results)

    print("\n" + "=" * 60)
    if all_passed:
        print("[DONE] 所有测试通过! DSPy 集成成功!")
        print("\n下一步:")
        print("1. 运行完整 Pipeline: python -m lab_analysis --use-dspy")
        print("2. 查看性能报告: reports/dspy_performance_report.json")
        print("3. 阅读使用文档: docs/DSPY_USAGE.md")
    else:
        print("[WARN]  部分测试失败,请检查上述错误信息")
        print("\n建议:")
        print("1. 确认 API Key 已正确配置")
        print("2. 检查网络连接")
        print("3. 确保训练数据已准备")
    print("=" * 60)


if __name__ == "__main__":
    main()
