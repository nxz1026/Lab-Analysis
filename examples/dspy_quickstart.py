#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy 快速开始示例

演示如何在 Lab-Analysis 项目中使用 DSPy
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def example_1_basic_usage():
    """示例 1: 基本使用 - 直接运行 DSPy 模块"""
    print("=" * 60)
    print("示例 1: 基本使用")
    print("=" * 60)
    
    try:
        from lab_analysis.dspy_modules import run_dspy_interpretation
        
        # 假设已有数据
        patient_id = "846552421134373347"
        data_dir = project_root / "data" / patient_id / "20260611_113946"
        
        if not data_dir.exists():
            print(f"[警告] 数据目录不存在: {data_dir}")
            print("请先运行完整 Pipeline 生成数据")
            return
        
        print(f"\n运行 DSPy 文献解读...")
        result = run_dspy_interpretation(patient_id, data_dir)
        
        print(f"\n[OK] 解读完成!")
        print(f"   可信度: {result['confidence']:.2f}")
        print(f"\n解读摘要:")
        print(result['interpretation'][:500] + "...")
        
    except ImportError as e:
        print(f"[错误] 无法导入 DSPy 模块: {e}")
        print("请先安装: pip install dspy-ai")
    except Exception as e:
        print(f"[错误] 运行失败: {e}")
        import traceback
        traceback.print_exc()


def example_2_custom_module():
    """示例 2: 自定义 DSPy 模块"""
    print("\n" + "=" * 60)
    print("示例 2: 自定义模块")
    print("=" * 60)
    
    try:
        import dspy
        
        # 定义一个简单的医学建议签名
        class MedicalAdviceSignature(dspy.Signature):
            """生成医学检查建议"""
            
            abnormal_indicators: str = dspy.InputField(
                desc="异常检验指标列表,如 'WBC升高, CRP升高'"
            )
            clinical_context: str = dspy.InputField(
                desc="临床背景,如 '患者发热3天,伴咳嗽'"
            )
            
            recommendations: str = dspy.OutputField(
                desc="具体的进一步检查建议,包括:\n"
                     "1. 需要补充的检验项目\n"
                     "2. 推荐的影像学检查\n"
                     "3. 专科会诊建议"
            )
        
        # 创建模块
        class MedicalAdvisor(dspy.Module):
            def __init__(self):
                super().__init__()
                self.advise = dspy.ChainOfThought(MedicalAdviceSignature)
            
            def forward(self, indicators, context):
                return self.advise(
                    abnormal_indicators=indicators,
                    clinical_context=context
                )
        
        # 配置 LLM (使用 DeepSeek)
        lm = dspy.LM(
            model='deepseek/deepseek-chat',
            api_key=os.environ.get('DEEPSEEK_API_KEY'),
            api_base='https://api.deepseek.com/v1'
        )
        dspy.configure(lm=lm)
        
        # 使用模块
        advisor = MedicalAdvisor()
        result = advisor(
            indicators="WBC 3.04↓, NEUT# 1.52↓, MONO% 17.80↑, CRP 17.44↑",
            context="患者反复发热,CRP-WBC分离现象"
        )
        
        print(f"\n[OK] 医学建议生成完成!")
        print(f"\n建议内容:")
        print(result.recommendations)
        
    except ImportError:
        print("[错误] 请先安装: pip install dspy-ai")
    except Exception as e:
        print(f"[错误] 运行失败: {e}")


def example_3_comparison():
    """示例 3: 对比原版和 DSPy 版本"""
    print("\n" + "=" * 60)
    print("示例 3: 性能对比")
    print("=" * 60)
    
    print("\n建议的对比测试流程:")
    print("1. 准备 10-20 个测试病例")
    print("2. 分别运行原版和 DSPy 版本")
    print("3. 邀请医生盲评打分")
    print("4. 统计各项指标差异")
    print("\n评估维度:")
    print("  - 完整性 (是否覆盖所有关键点)")
    print("  - 准确性 (医学知识是否正确)")
    print("  - 可读性 (表达是否清晰)")
    print("  - 实用性 (对临床决策的帮助)")


def main():
    """主函数"""
    print("\n" + "[LAB]" * 30)
    print("Lab-Analysis DSPy 快速开始")
    print("[LAB]" * 30 + "\n")
    
    print("请选择要运行的示例:")
    print("1. 基本使用 - 运行 DSPy 文献解读")
    print("2. 自定义模块 - 创建医学建议生成器")
    print("3. 性能对比 - 查看对比测试方法")
    print("0. 退出")
    
    try:
        choice = input("\n请输入选择 (0-3): ").strip()
        
        if choice == "1":
            example_1_basic_usage()
        elif choice == "2":
            example_2_custom_module()
        elif choice == "3":
            example_3_comparison()
        elif choice == "0":
            print("\n再见! [HELLO]")
            return
        else:
            print("\n[错误] 无效选择")
    except KeyboardInterrupt:
        print("\n\n已取消")
    except Exception as e:
        print(f"\n[错误] {e}")
    
    print("\n" + "=" * 60)
    print("更多信息请查看: docs/DSPY_INTEGRATION.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
