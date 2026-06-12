#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy LLM 配置测试

测试 DSPy 与 DeepSeek API 的连接
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


def test_deepseek_connection():
    """测试 DeepSeek API 连接"""
    print("=" * 60)
    print("测试: DSPy + DeepSeek API 连接")
    print("=" * 60)
    
    try:
        import dspy
        
        # 获取 API 密钥
        api_key = os.environ.get('DEEPSEEK_API_KEY')
        if not api_key:
            print("[FAIL] 未找到 DEEPSEEK_API_KEY 环境变量")
            return False
        
        print(f"[OK] 找到 API 密钥: {api_key[:20]}...")
        
        # 配置 DSPy 使用 DeepSeek
        print("\n配置 DSPy LM...")
        lm = dspy.LM(
            model='deepseek/deepseek-chat',
            api_key=api_key,
            api_base='https://api.deepseek.com/v1'
        )
        dspy.configure(lm=lm)
        print(f"[OK] LM 配置成功")
        print(f"   模型: deepseek-chat")
        
        # 测试简单调用
        print("\n测试 LLM 调用...")
        predictor = dspy.Predict("question -> answer")
        
        result = predictor(question="什么是DSPy?请用一句话回答。")
        
        print(f"[OK] LLM 调用成功!")
        print(f"   问题: 什么是DSPy?")
        print(f"   回答: {result.answer}")
        
        return True
        
    except Exception as e:
        print(f"[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("\n" + "[LINK]" * 30)
    print("DSPy LLM 配置测试")
    print("[LINK]" * 30 + "\n")
    
    success = test_deepseek_connection()
    
    print("\n" + "=" * 60)
    if success:
        print("[DONE] DSPy + DeepSeek 配置成功!")
        print("\n现在可以:")
        print("1. 运行文献解读模块")
        print("2. 准备训练数据")
        print("3. 编译和优化模块")
    else:
        print("[WARN]  配置失败,请检查:")
        print("1. API 密钥是否正确")
        print("2. 网络连接是否正常")
        print("3. API 配额是否充足")
    print("=" * 60)


if __name__ == "__main__":
    main()
