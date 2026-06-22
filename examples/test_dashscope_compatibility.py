#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 DashScope Qwen-VL 与 DSPy 的兼容性

找出正确的模型名称格式和 API 端点配置
"""

import os

from dotenv import load_dotenv

load_dotenv()


def test_dashscope_direct():
    """测试 1: 直接调用 DashScope API (不使用 DSPy)"""
    print("=" * 60)
    print("测试 1: 直接调用 DashScope API")
    print("=" * 60)

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("[FAIL] 未找到 DASHSCOPE_API_KEY")
        return False

    try:
        import requests

        # 直接使用 DashScope API
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

        payload = {
            "model": "qwen-vl-plus",
            "input": {"messages": [{"role": "user", "content": [{"text": "请描述这张图片"}]}]},
        }

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        print("[测试] 发送请求到 DashScope...")
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            print("[OK] DashScope API 调用成功")
            return True
        else:
            print(f"[FAIL] API 调用失败: {response.status_code}")
            print(f"   响应: {response.text[:200]}")
            return False

    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        return False


def test_litellm_qwen():
    """测试 2: 使用 LiteLLM 调用 Qwen-VL"""
    print("\n" + "=" * 60)
    print("测试 2: LiteLLM + Qwen-VL")
    print("=" * 60)

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("[FAIL] 未找到 DASHSCOPE_API_KEY")
        return False

    try:
        import litellm

        # 尝试不同的模型名称格式
        model_formats = [
            "dashscope/qwen-vl-plus",
            "qwen_vl_plus",
        ]

        for model_name in model_formats:
            try:
                print(f"[测试] 尝试模型: {model_name}")

                response = litellm.completion(  # noqa: F841 — 仅用于验证调用成功
                    model=model_name,
                    messages=[{"role": "user", "content": "Hello"}],
                    api_key=api_key,
                    api_base="https://dashscope.aliyuncs.com/api/v1",
                )

                print(f"[OK] LiteLLM 调用成功: {model_name}")
                return True

            except Exception as e:
                print(f"   [FAIL] 失败: {str(e)[:100]}")
                continue

        print("[FAIL] 所有模型格式都失败")
        return False

    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        return False


def test_dspy_simple():
    """测试 3: 使用 DSPy 简单调用"""
    print("\n" + "=" * 60)
    print("测试 3: DSPy 简单调用")
    print("=" * 60)

    api_key = os.environ.get("DASHSCOPE_API_KEY")
    if not api_key:
        print("[FAIL] 未找到 DASHSCOPE_API_KEY")
        return False

    try:
        import dspy

        # 配置 DSPy
        lm = dspy.LM(
            model="openai/qwen-vl-plus",  # 尝试 openai 兼容模式
            api_key=api_key,
            api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        dspy.configure(lm=lm)
        print("[OK] DSPy LM 配置成功")

        # 简单测试
        predictor = dspy.Predict("question -> answer")
        result = predictor(question="什么是DSPy?")

        print("[OK] DSPy 调用成功")
        print(f"   回答: {result.answer[:100]}...")

        return True

    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "[TOOL]" * 30)
    print("DashScope Qwen-VL 配置诊断")
    print("[TOOL]" * 30 + "\n")

    results = {}

    results["DashScope Direct API"] = test_dashscope_direct()
    results["LiteLLM"] = test_litellm_qwen()
    results["DSPy Simple"] = test_dspy_simple()

    print("\n" + "=" * 60)
    print("[STATS] 诊断结果")
    print("=" * 60)

    for test_name, result in results.items():
        status = "[OK] 通过" if result else "[FAIL] 失败"
        print(f"{test_name}: {status}")

    passed = sum(1 for r in results.values() if r)
    total = len(results)

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n[DONE] 所有测试通过! DashScope 配置正确!")
    else:
        print("\n[WARN]  部分测试失败,请检查:")
        print("1. API Key 是否正确")
        print("2. 网络连接是否正常")
        print("3. 模型是否可用")

    print("=" * 60)


if __name__ == "__main__":
    main()
