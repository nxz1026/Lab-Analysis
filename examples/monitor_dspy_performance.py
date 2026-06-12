#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DSPy 性能监控和评估工具

对比标准模式和 DSPy 模式的输出质量,生成性能报告
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


def load_dspy_samples(data_file: Path = None) -> List[Dict]:
    """加载 DSPy 训练样本"""
    if data_file is None:
        data_file = Path(__file__).parent.parent / "data" / "dspy_training_enhanced.jsonl"
    
    samples = []
    with open(data_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                samples.append(json.loads(line))
    
    return samples


def evaluate_interpretation_quality(interpretation: str) -> Dict:
    """
    评估文献解读质量
    
    Returns:
        Quality metrics dict
    """
    metrics = {
        'length': len(interpretation),
        'has_sections': False,
        'has_mechanism': False,
        'has_clinical_significance': False,
        'has_recommendations': False,
        'section_count': 0
    }
    
    # 检查长度
    if metrics['length'] > 1000:
        metrics['length_score'] = 'excellent'
    elif metrics['length'] > 500:
        metrics['length_score'] = 'good'
    else:
        metrics['length_score'] = 'poor'
    
    # 检查结构化
    section_keywords = [
        '病理生理',
        '临床意义',
        '建议',
        '机制',
        '治疗',
        '诊断'
    ]
    
    found_sections = [kw for kw in section_keywords if kw in interpretation]
    metrics['found_sections'] = found_sections
    metrics['section_count'] = len(found_sections)
    
    if metrics['section_count'] >= 3:
        metrics['structure_score'] = 'excellent'
    elif metrics['section_count'] >= 2:
        metrics['structure_score'] = 'good'
    else:
        metrics['structure_score'] = 'poor'
    
    # 综合评分
    if metrics['length_score'] == 'excellent' and metrics['structure_score'] == 'excellent':
        metrics['overall_score'] = 9.0
    elif metrics['length_score'] in ['excellent', 'good'] and metrics['structure_score'] in ['excellent', 'good']:
        metrics['overall_score'] = 7.5
    else:
        metrics['overall_score'] = 5.0
    
    return metrics


def compare_modes(samples: List[Dict]) -> Dict:
    """
    对比标准模式和 DSPy 模式的性能
    
    Args:
        samples: 训练样本列表
    
    Returns:
        Comparison results
    """
    print("=" * 60)
    print("性能对比分析")
    print("=" * 60)
    
    results = {
        'standard': [],
        'dspy': [],
        'improvement': {}
    }
    
    for i, sample in enumerate(samples):
        print(f"\n样本 {i+1}/{len(samples)}: {sample.get('patient_id', 'unknown')}")
        
        interpretation = sample.get('interpretation', '')
        
        # 评估质量
        quality = evaluate_interpretation_quality(interpretation)
        
        print(f"  长度: {quality['length']} 字符")
        print(f"  结构: {quality['structure_score']} ({quality['section_count']} 个章节)")
        print(f"  综合评分: {quality['overall_score']}/10")
        
        # 根据来源判断模式
        if sample.get('source') == 'manual_annotation':
            results['dspy'].append(quality)
            print(f"  模式: DSPy (手动标注示例)")
        else:
            results['standard'].append(quality)
            print(f"  模式: 标准 Pipeline")
    
    # 计算平均指标
    def calc_avg(qualities):
        if not qualities:
            return {}
        
        avg_length = sum(q['length'] for q in qualities) / len(qualities)
        avg_score = sum(q['overall_score'] for q in qualities) / len(qualities)
        avg_sections = sum(q['section_count'] for q in qualities) / len(qualities)
        
        return {
            'avg_length': round(avg_length),
            'avg_score': round(avg_score, 2),
            'avg_sections': round(avg_sections, 1),
            'count': len(qualities)
        }
    
    standard_stats = calc_avg(results['standard'])
    dspy_stats = calc_avg(results['dspy'])
    
    # 计算提升
    if standard_stats and dspy_stats:
        length_improvement = ((dspy_stats['avg_length'] - standard_stats['avg_length']) / 
                             standard_stats['avg_length'] * 100)
        score_improvement = ((dspy_stats['avg_score'] - standard_stats['avg_score']) / 
                            standard_stats['avg_score'] * 100)
        
        results['improvement'] = {
            'length': f"+{length_improvement:.1f}%",
            'score': f"+{score_improvement:.1f}%",
            'sections': f"{dspy_stats['avg_sections']} vs {standard_stats['avg_sections']}"
        }
    
    results['standard_stats'] = standard_stats
    results['dspy_stats'] = dspy_stats
    
    return results


def generate_performance_report(results: Dict, output_file: Path):
    """
    生成性能报告
    
    Args:
        results: 对比结果
        output_file: 输出文件路径
    """
    print("\n" + "=" * 60)
    print("生成性能报告")
    print("=" * 60)
    
    report = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': {
            'standard_mode': results.get('standard_stats', {}),
            'dspy_mode': results.get('dspy_stats', {}),
            'improvement': results.get('improvement', {})
        },
        'detailed_results': results
    }
    
    # 保存 JSON 报告
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"[成功] 报告已保存到: {output_file}")
    
    # 打印摘要
    print("\n" + "=" * 60)
    print("[STATS] 性能对比摘要")
    print("=" * 60)
    
    std = results.get('standard_stats', {})
    dspy = results.get('dspy_stats', {})
    imp = results.get('improvement', {})
    
    if std and dspy:
        print(f"\n标准模式:")
        print(f"  平均长度: {std.get('avg_length', 'N/A')} 字符")
        print(f"  平均评分: {std.get('avg_score', 'N/A')}/10")
        print(f"  平均章节: {std.get('avg_sections', 'N/A')}")
        
        print(f"\nDSPy 模式:")
        print(f"  平均长度: {dspy.get('avg_length', 'N/A')} 字符")
        print(f"  平均评分: {dspy.get('avg_score', 'N/A')}/10")
        print(f"  平均章节: {dspy.get('avg_sections', 'N/A')}")
        
        print(f"\n提升幅度:")
        print(f"  长度: {imp.get('length', 'N/A')}")
        print(f"  评分: {imp.get('score', 'N/A')}")
        print(f"  章节: {imp.get('sections', 'N/A')}")
    
    print("\n" + "=" * 60)


def main():
    """主函数"""
    print("\n" + "[SEARCH]" * 30)
    print("DSPy 性能监控工具")
    print("[SEARCH]" * 30 + "\n")
    
    # 1. 加载训练样本
    print("[步骤 1] 加载训练样本...")
    samples = load_dspy_samples()
    print(f"       已加载 {len(samples)} 个样本\n")
    
    # 2. 对比性能
    print("[步骤 2] 对比标准模式 vs DSPy 模式...")
    results = compare_modes(samples)
    
    # 3. 生成报告
    print("\n[步骤 3] 生成性能报告...")
    output_file = Path(__file__).parent.parent / "reports" / "dspy_performance_report.json"
    generate_performance_report(results, output_file)
    
    print("\n" + "=" * 60)
    print("[DONE] 性能监控完成!")
    print("=" * 60)
    print(f"\n报告位置: {output_file}")
    print("\n建议:")
    print("1. 查看完整报告了解详细对比")
    print("2. 如果 DSPy 提升不明显,考虑增加训练数据")
    print("3. 定期运行此工具监控性能变化")
    print("=" * 60)


if __name__ == "__main__":
    main()
