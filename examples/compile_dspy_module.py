#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy 模块编译和优化脚本

使用训练数据编译和优化 LiteratureInterpreterModule
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
import sys
sys.path.insert(0, str(project_root))


def configure_dspy():
    """配置 DSPy 和 LLM"""
    import dspy
    
    # 获取 API 密钥
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        raise ValueError("未找到 DEEPSEEK_API_KEY 环境变量")
    
    # 配置 DeepSeek LM
    lm = dspy.LM(
        model='deepseek/deepseek-chat',
        api_key=api_key,
        api_base='https://api.deepseek.com/v1'
    )
    
    dspy.configure(lm=lm)
    print(f"[配置] DSPy LM 已配置: deepseek-chat")
    
    return lm


def load_training_data(data_path: Path = None):
    """加载训练数据"""
    if data_path is None:
        data_path = project_root / "data" / "dspy_training.jsonl"
    
    if not data_path.exists():
        raise FileNotFoundError(f"训练数据文件不存在: {data_path}")
    
    samples = []
    with open(data_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    
    print(f"[数据] 加载 {len(samples)} 个训练样本")
    return samples


def prepare_dspy_examples(samples):
    """将样本转换为 DSPy Example 格式"""
    import dspy
    
    examples = []
    
    for sample in samples:
        example = dspy.Example(
            patient_id=sample['patient_id'],
            analysis_results=sample['analysis_results'],
            literature_results=sample['literature_results'],
            interpretation=sample['interpretation']
        ).with_inputs('patient_id', 'analysis_results', 'literature_results')
        
        examples.append(example)
    
    print(f"[转换] 准备 {len(examples)} 个 DSPy Examples")
    return examples


def compile_module(examples, num_threads=2):
    """编译和优化 DSPy 模块"""
    from lab_analysis.dspy_modules import LiteratureInterpreterModule, compile_interpreter
    
    print("\n" + "=" * 60)
    print("开始编译 DSPy 模块")
    print("=" * 60)
    
    # 分割训练集和验证集
    train_size = int(len(examples) * 0.7)
    train_examples = examples[:train_size]
    val_examples = examples[train_size:]
    
    print(f"[数据] 训练集: {len(train_examples)}, 验证集: {len(val_examples)}")
    
    # 转换为字典格式(compile_interpreter 需要)
    train_data = []
    for ex in train_examples:
        train_data.append({
            'patient_id': ex.patient_id,
            'analysis_results': ex.analysis_results,
            'literature_results': ex.literature_results,
            'interpretation': ex.interpretation
        })
    
    dev_data = []
    for ex in val_examples:
        dev_data.append({
            'patient_id': ex.patient_id,
            'analysis_results': ex.analysis_results,
            'literature_results': ex.literature_results,
            'interpretation': ex.interpretation
        })
    
    # 编译模块
    print(f"\n[编译] 使用 BootstrapFewShot 优化器...")
    
    try:
        compiled_module = compile_interpreter(
            train_data=train_data,
            dev_data=dev_data
        )
        
        print(f"\n[成功] 模块编译完成!")
        
        # 保存编译后的模块
        output_dir = project_root / "models" / "dspy"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        save_path = output_dir / "literature_interpreter_compiled.json"
        compiled_module.save(save_path)
        print(f"[保存] 编译后的模块已保存到: {save_path}")
        
        return compiled_module
        
    except Exception as e:
        print(f"\n[错误] 编译失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_compiled_module(compiled_module, examples):
    """测试编译后的模块"""
    if compiled_module is None:
        print("[跳过] 模块未编译")
        return
    
    print("\n" + "=" * 60)
    print("测试编译后的模块")
    print("=" * 60)
    
    # 选择前2个样本进行测试
    test_samples = examples[:2]
    
    for i, example in enumerate(test_samples, 1):
        print(f"\n[测试 {i}] 患者ID: {example.patient_id}")
        
        try:
            result = compiled_module(
                patient_id=example.patient_id,
                analysis_results=example.analysis_results,
                literature_results=example.literature_results
            )
            
            print(f"  [成功] 生成解读 ({len(result.interpretation)} 字符)")
            print(f"  [置信度] {result.confidence}")
            print(f"  [预览] {result.interpretation[:200]}...")
            
        except Exception as e:
            print(f"  [失败] {e}")


def main():
    """主函数"""
    print("\n" + "🔧" * 30)
    print("DSPy 模块编译工具")
    print("🔧" * 30 + "\n")
    
    try:
        # Step 1: 配置 DSPy
        print("[Step 1] 配置 DSPy...")
        configure_dspy()
        
        # Step 2: 加载训练数据
        print("\n[Step 2] 加载训练数据...")
        samples = load_training_data()
        
        if len(samples) < 3:
            print("\n[警告] 训练样本不足 (至少需要3个)")
            print("建议:")
            print("1. 运行更多患者的完整 Pipeline")
            print("2. 或者手动标注一些示例数据")
            return
        
        # Step 3: 准备 DSPy Examples
        print("\n[Step 3] 准备 DSPy Examples...")
        examples = prepare_dspy_examples(samples)
        
        # Step 4: 编译模块
        print("\n[Step 4] 编译和优化模块...")
        compiled_module = compile_module(examples)
        
        # Step 5: 测试编译后的模块
        print("\n[Step 5] 测试编译结果...")
        test_compiled_module(compiled_module, examples)
        
        print("\n" + "=" * 60)
        print("[完成] DSPy 模块编译完成!")
        print("=" * 60)
        print("\n下一步:")
        print("1. 在 Pipeline 中使用编译后的模块")
        print("2. 查看 docs/DSPY_INTEGRATION.md 了解集成方法")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"\n[错误] 编译过程失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
