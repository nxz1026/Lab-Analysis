# DSPy 集成指南

## 📋 目录

- [概述](#概述)
- [安装](#安装)
- [架构设计](#架构设计)
- [使用步骤](#使用步骤)
- [训练与优化](#训练与优化)
- [性能对比](#性能对比)
- [最佳实践](#最佳实践)

---

## 概述

本项目已集成 **DSPy (Declarative Self-improving Python)** 框架,用于优化 LLM 驱动的医学分析流程。

### 为什么使用 DSPy?

| 传统 Prompt 工程 | DSPy 方法 |
|-----------------|----------|
| 手动调试 prompt | 声明式模块定义 |
| 难以复现结果 | 系统化的版本控制 |
| 依赖经验 | 自动优化和编译 |
| 黑盒调优 | 可解释的优化过程 |

### 适用场景

✅ **推荐使用 DSPy 的步骤:**
1. **文献解读** (`literature_interpreter.py`) - 生成循证医学解读
2. **最终报告** (`gen_final_report.py`) - 综合多源数据生成报告
3. **检验数据提取** (`extract_lab_data.py`) - 从图片提取结构化数据

❌ **不推荐使用:**
- 纯数据处理步骤 (data_loader, data_analyzer)
- 文件操作 (organize_local_files)

---

## 安装

```bash
# 安装 DSPy
pip install dspy-ai

# 验证安装
python -c "import dspy; print(dspy.__version__)"
```

### 配置 LLM

在 `.env` 文件中添加 DSPy 配置:

```bash
# DSPy 使用的 LLM (默认使用 DeepSeek)
DSPY_LLM_MODEL=deepseek-chat
DSPY_API_KEY=your_deepseek_api_key
```

或在代码中配置:

```python
import dspy

# 配置 DeepSeek
lm = dspy.LM(
    model='deepseek/deepseek-chat',
    api_key=os.environ['DEEPSEEK_API_KEY'],
    api_base='https://api.deepseek.com/v1'
)
dspy.configure(lm=lm)
```

---

## 架构设计

### 目录结构

```
lab_analysis/
├── dspy_modules/              # DSPy 模块
│   ├── __init__.py
│   ├── literature_interpreter.py    # 文献解读模块
│   ├── final_report_generator.py    # 报告生成模块 (待开发)
│   └── lab_data_extractor.py        # 数据提取模块 (待开发)
├── literature_interpreter.py  # 原版 (保留作为 fallback)
├── gen_final_report.py        # 原版
└── extract_lab_data.py        # 原版
```

### 核心概念

1. **Signature (签名)**: 定义输入输出字段和描述
2. **Module (模块)**: 封装 LLM 调用逻辑
3. **Optimizer (优化器)**: 自动优化 prompts
4. **Metric (指标)**: 评估输出质量

---

## 使用步骤

### 方式 1: 直接使用 (无需训练)

```python
from lab_analysis.dspy_modules import run_dspy_interpretation
from pathlib import Path

# 运行 DSPy 版本的文献解读
result = run_dspy_interpretation(
    patient_id="846552421134373347",
    data_dir=Path("data/846552421134373347/20260611_113946")
)

print(f"解读可信度: {result['confidence']:.2f}")
print(f"解读内容:\n{result['interpretation']}")
```

### 方式 2: 命令行运行

```bash
# 设置环境变量
export ANALYSIS_TS=20260611_113946

# 运行 DSPy 文献解读
python -m lab_analysis.dspy_modules.literature_interpreter \
    --patient-id 846552421134373347
```

### 方式 3: 集成到 Pipeline

修改 `pipeline.py`,添加 DSPy 选项:

```python
parser.add_argument("--use-dspy", action="store_true", 
                   help="使用 DSPy 优化的模块")

# 在步骤⑥中
if args.use_dspy:
    from lab_analysis.dspy_modules import run_dspy_interpretation
    result = run_dspy_interpretation(deid, paths["data_dir"])
else:
    # 使用原版
    rc = run_step("⑥ 循证解读", "literature_interpreter", pid_arg, ts_env)
```

---

## 训练与优化

### 准备训练数据

创建训练数据集 `train_data.json`:

```json
[
  {
    "patient_id": "patient_001",
    "analysis_results": {
      "abnormal_indicators": ["WBC", "CRP"],
      "statistics": {...}
    },
    "literature_results": {
      "papers": [...]
    },
    "expert_interpretation": "专家标注的标准解读..."
  }
]
```

### 编译优化模块

```python
from lab_analysis.dspy_modules.literature_interpreter import (
    LiteratureInterpreterModule,
    compile_interpreter
)
import json

# 加载训练数据
with open('train_data.json', 'r') as f:
    train_data = json.load(f)

# 分割训练集和验证集
train_set = train_data[:80]
dev_set = train_data[80:]

# 编译优化
compiled_module = compile_interpreter(train_set, dev_set)

# 保存优化后的模块
compiled_module.save('compiled_interpreter.pkl')
```

### 加载已编译模块

```python
from lab_analysis.dspy_modules import LiteratureInterpreterModule

# 加载
module = LiteratureInterpreterModule()
module.load('compiled_interpreter.pkl')

# 使用
result = module(patient_id, analysis_results, literature_results)
```

---

## 性能对比

### 预期改进

| 指标 | 原版 | DSPy (未训练) | DSPy (已训练) |
|------|------|--------------|--------------|
| 解读完整性 | 70% | 75% | **90%** |
| 临床相关性 | 65% | 70% | **88%** |
| 格式规范性 | 60% | 80% | **95%** |
| 推理时间 | 5s | 6s | 6s |

### 评估方法

```python
def evaluate_interpretation(pred, ground_truth):
    """评估解读质量"""
    scores = {
        'completeness': check_sections(pred),
        'relevance': semantic_similarity(pred, ground_truth),
        'accuracy': factual_consistency(pred, ground_truth)
    }
    return scores
```

---

## 最佳实践

### 1. 渐进式迁移

不要一次性替换所有模块,建议顺序:

```
Phase 1: literature_interpreter (2周)
  ↓
Phase 2: gen_final_report (2周)
  ↓
Phase 3: extract_lab_data (3周)
```

### 2. A/B 测试

同时运行原版和 DSPy 版本,对比结果:

```python
# 并行运行
original_result = run_original_interpretation(...)
dspy_result = run_dspy_interpretation(...)

# 人工评估
compare_results(original_result, dspy_result)
```

### 3. 持续优化

定期收集新病例,重新训练:

```bash
# 每月执行
python scripts/retrain_dspy_modules.py \
    --new-data data/new_cases/*.json \
    --output compiled_modules/
```

### 4. 监控指标

跟踪关键指标:

- **LLM 调用次数**: 优化后应减少
- **平均响应时间**: 应在可接受范围
- **用户满意度**: 医生反馈评分
- **错误率**: 异常输出比例

---

## 常见问题

### Q1: DSPy 会增加多少延迟?

A: 通常增加 10-20%,但通过缓存和优化可以降到 5% 以内。

### Q2: 需要多少训练数据?

A: 
- 最小: 20-30 个高质量样本
- 推荐: 100+ 样本
- 理想: 500+ 样本

### Q3: 如何回退到原版?

A: 保留原版文件,通过命令行参数切换:

```bash
# 使用原版
python -m lab_analysis --patient-id XXX

# 使用 DSPy
python -m lab_analysis --patient-id XXX --use-dspy
```

### Q4: DSPy 支持哪些 LLM?

A: 支持主流模型:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- DeepSeek
- 智谱 AI
- 阿里云 Qwen

---

## 下一步计划

- [ ] 开发 `final_report_generator.py`
- [ ] 开发 `lab_data_extractor.py`
- [ ] 创建训练数据集 (至少 50 个病例)
- [ ] 实现 A/B 测试框架
- [ ] 添加性能监控面板

---

## 参考资料

- [DSPy 官方文档](https://dspy.ai/)
- [DSPy GitHub](https://github.com/stanfordnlp/dspy)
- [医学 LLM 应用最佳实践](https://arxiv.org/abs/2307.03172)
