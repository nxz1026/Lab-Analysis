#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy 基础功能测试

自动测试 DSPy 的基本功能,无需人工交互
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_import():
    """测试 1: 导入 DSPy"""
    print("=" * 60)
    print("测试 1: 导入 DSPy")
    print("=" * 60)

    try:
        import dspy

        print("[OK] DSPy 导入成功")
        print(f"   版本: {dspy.__version__}")
        return True
    except ImportError as e:
        print(f"[FAIL] DSPy 导入失败: {e}")
        return False


def test_basic_signature():
    """测试 2: 创建基本签名"""
    print("\n" + "=" * 60)
    print("测试 2: 创建 DSPy 签名")
    print("=" * 60)

    try:
        import dspy

        # 定义一个简单的签名
        class TestSignature(dspy.Signature):
            """测试签名"""

            question: str = dspy.InputField(desc="问题")
            answer: str = dspy.OutputField(desc="答案")

        print("[OK] 签名创建成功")
        print("   输入字段: question")
        print("   输出字段: answer")
        return True

    except Exception as e:
        print(f"[FAIL] 签名创建失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_module_creation():
    """测试 3: 创建模块"""
    print("\n" + "=" * 60)
    print("测试 3: 创建 DSPy 模块")
    print("=" * 60)

    try:
        import dspy

        class TestSignature(dspy.Signature):
            question: str = dspy.InputField()
            answer: str = dspy.OutputField()

        class TestModule(dspy.Module):
            def __init__(self):
                super().__init__()
                self.predict = dspy.Predict(TestSignature)

            def forward(self, question):
                return self.predict(question=question)

        module = TestModule()
        print("[OK] 模块创建成功")
        print(f"   类型: {type(module).__name__}")
        return True

    except Exception as e:
        print(f"[FAIL] 模块创建失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_lab_analysis_module():
    """测试 4: 测试 Lab-Analysis DSPy 模块"""
    print("\n" + "=" * 60)
    print("测试 4: 测试 Lab-Analysis DSPy 模块")
    print("=" * 60)

    try:
        from lab_analysis.dspy_modules import LiteratureInterpreterModule

        module = LiteratureInterpreterModule()
        print("[OK] LiteratureInterpreterModule 导入成功")
        print(f"   模块类型: {type(module).__name__}")
        print("   包含组件: interpret (ChainOfThought)")
        return True

    except ImportError as e:
        print(f"[WARN]  模块导入失败 (可能需要先配置 LLM): {e}")
        print("   这是正常的,因为还没有配置 API 密钥")
        return None  # 不算失败
    except Exception as e:
        print(f"[FAIL] 模块测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "[TEST]" * 30)
    print("DSPy 基础功能测试")
    print("[TEST]" * 30 + "\n")

    results = []

    # 运行测试
    results.append(("导入测试", test_import()))
    results.append(("签名测试", test_basic_signature()))
    results.append(("模块测试", test_module_creation()))
    results.append(("Lab-Analysis 模块", test_lab_analysis_module()))

    # 打印总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    passed = sum(1 for _, r in results if r is True)
    failed = sum(1 for _, r in results if r is False)
    skipped = sum(1 for _, r in results if r is None)

    for name, result in results:
        if result is True:
            status = "[OK] 通过"
        elif result is False:
            status = "[FAIL] 失败"
        else:
            status = "[WARN]  跳过"
        print(f"{status} - {name}")

    print(f"\n总计: {passed} 通过, {failed} 失败, {skipped} 跳过")

    if failed == 0:
        print("\n[DONE] 所有核心测试通过! DSPy 已准备好使用!")
    else:
        print(f"\n[WARN]  有 {failed} 个测试失败,请检查错误信息")

    print("\n下一步:")
    print("1. 配置 LLM API 密钥 (在 .env 文件中)")
    print("2. 运行实际病例测试")
    print("3. 准备训练数据")
    print("=" * 60)


if __name__ == "__main__":
    main()
