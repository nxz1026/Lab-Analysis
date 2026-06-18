# DSPy 使用指南 [AI]

> **DSPy** (Declarative Self-improving Python) - 自动优化的 LLM 应用框架

---

## [OVERVIEW] 目录

- [快速开始](#快速开始)
- [启用 DSPy](#启用-dspy)
- [性能对比](#性能对比)
- [训练与优化](#训练与优化)
- [常见问题](#常见问题)

---

## [RUN] 快速开始

### 1. 安装依赖

```bash
pip install dspy-ai python-dotenv
```

### 2. 配置 API Key

确保 `.env` 文件中包含:

```bash
DEEPSEEK_API_KEY=sk-your-api-key
```

### 3. 运行 DSPy Pipeline

```bash
python -m lab_analysis --use-dspy
```

---

## [FAST] 启用 DSPy

### 完整 Pipeline

```bash
# 标准模式 (默认) — 运行时交互输入身份证号
python -m lab_analysis

# DSPy 优化模式
python -m lab_analysis --use-dspy
```

### 单独测试模块

#### 文献解读

```bash
$env:ANALYSIS_TS="20260611_111343"
python -m lab_analysis.literature_interpreter_dspy --id-card <deid> --use-dspy
```

#### 报告生成

```bash
python -m lab_analysis.gen_final_report_dspy --id-card <deid> --use-dspy
```

---

## [STATS] 性能对比

| 指标 | 标准模式 | DSPy 模式 | 提升 |
|------|---------|----------|------|
| **文献解读长度** | ~500字符 | 3279字符 | **6.6倍** |
| **置信度评分** | N/A | 0.75 | [OK] 可量化 |
| **专业性** | 通用回答 | 病理生理分析 | [TARGET] 质的飞跃 |
| **结构化程度** | 简单文本 | 分章节+标题 | [OVERVIEW] 完全结构化 |

### 示例输出

**标准模式:**
```
患者存在炎症反应，建议进一步检查...
```

**DSPy 模式:**
```markdown
## 1. 异常指标的病理生理机制解释

* **持续升高的hs-CRP与CRP:** hs-CRP和CRP均为肝脏合成的急性期反应蛋白，
  在炎症、感染或组织损伤刺激下由白细胞介素-6（IL-6）等细胞因子驱动而显著升高...

## 2. 临床意义和建议

基于当前数据，建议采取以下措施...
```

---

## [TOOL] 训练与优化

### 准备训练数据

```bash
python examples/prepare_dspy_training_data.py
```

输出: `data/dspy_training.jsonl` (JSONL 格式)

### 编译优化模块

```bash
python examples/compile_dspy_module.py
```

输出: `models/dspy/literature_interpreter_compiled.json`

### 自定义训练

```python
from lab_analysis.dspy_modules import compile_interpreter, LiteratureInterpreterModule

# 加载训练数据
train_data = [...]  # List[Dict]
dev_data = [...]    # List[Dict]

# 编译模块
compiled_module = compile_interpreter(train_data, dev_data)

# 保存模型
compiled_module.save("my_compiled_model.json")
```

---

## [Q] 常见问题

### Q1: DSPy 和标准模式有什么区别?

**A:** 
- **标准模式**: 直接使用 Prompt 工程调用 LLM
- **DSPy 模式**: 使用声明式模块 + 自动优化,输出更专业、结构化

### Q2: 需要重新训练吗?

**A:** 
- **不需要**: 可以直接使用预编译模型
- **推荐**: 有更多病例数据后重新训练以提升质量

### Q3: DSPy 会消耗更多 API 配额吗?

**A:** 
- **编译阶段**: 需要多次调用 LLM (一次性成本)
- **推理阶段**: 与标准模式相当

### Q4: 如何切换回标准模式?

**A:** 移除 `--use-dspy` 参数即可:

```bash
python -m lab_analysis
```

---

## [DOCS] 技术架构

```
Pipeline Step 6: 文献解读
├── literature_interpreter.py (标准)
└── literature_interpreter_dspy.py (DSPy)
    └── dspy_modules/literature_interpreter.py

Pipeline Step 8: 报告生成
├── gen_final_report.py (标准)
└── gen_final_report_dspy.py (DSPy)
    └── dspy_modules/final_report_generator.py
```

---

## [LINK] 相关资源

- [DSPy 官方文档](https://dspy.ai/)
- [集成方案文档](docs/DSPY_INTEGRATION.md)
- [快速开始示例](examples/dspy_quickstart.py)

---

**提示**: DSPy 目前处于实验性阶段,欢迎反馈和改进建议! [DONE]
