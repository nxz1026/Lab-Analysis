# Evidence Grading — 文献证据等级打分

Pipeline 步骤⑤b，对步骤⑤ PubMed 文献检索结果做二次筛选，按 5 个维度独立打分后加权汇总，保留 top-k。

---

## 设计动机

步骤⑤ (`literature_searcher.py`) 是基于关键词的 PubMed 召回，**不做证据强度判断**：

- 一篇 1995 年的老综述，可能和 2024 年的 RCT 排在同一行
- 一篇只有 title 没 abstract 的"半篇论文"，和完整 abstract 论文等权
- 主题相关性靠关键词共现判断，容易把沾边的论文都拉进来

步骤⑤b 在保留步骤⑤所有召回结果的前提下，加一层**纯规则的证据等级打分**，把排序和筛选做得更稳健。

### 为什么不调 LLM？

- **可重复**：纯函数化打分，同一份输入永远得到同一份输出
- **可测试**：32 个单测覆盖 5 维度 + E2E，无需 mock LLM
- **零延迟**：本地内存计算，毫秒级
- **零成本**：不消耗 API 配额

LLM 的价值放在步骤⑥（解读），不在打分。

---

## 5 个打分维度

| 维度 | 范围 | 关键信号 |
|------|------|----------|
| `topic_match` | 0.0 ~ 1.0 | title + abstract 命中主题关键词数 / 主题词库总数 |
| `evidence_level` | 0.0 ~ 1.0 | publication_types 标识 RCT > cohort > review > case report > 无标识 |
| `recency` | 0.0 ~ 1.0 | year 距今的衰减（5年内最高，>10年衰减，>20年趋零） |
| `sample_size` | 0.0 ~ 1.0 | abstract 中提取的患者数 n=N / 大样本阈值 |
| `parse_quality` | 0.0 ~ 1.0 | abstract 非空 + 非占位符 + 非错位（避免把作者列表当摘要） |

每个维度独立打分 + 返回 reason 字符串 → `reasons` 字段拼出可解释链。

---

## 3 种场景权重

不同临床问题对维度偏好不同，权重随之变化：

```python
SCENARIO_WEIGHTS = {
    "early_diagnosis": {
        # 早期诊断：偏新颖 + 时效
        "topic_match": 0.35, "evidence_level": 0.25, "recency": 0.20,
        "sample_size": 0.10, "parse_quality": 0.10,
    },
    "differential_diagnosis": {
        # 鉴别诊断：偏对比研究 + 样本量
        "topic_match": 0.30, "evidence_level": 0.25, "recency": 0.10,
        "sample_size": 0.25, "parse_quality": 0.10,
    },
    "prognosis": {
        # 预后：偏证据等级（队列研究）+ 样本量
        "topic_match": 0.25, "evidence_level": 0.35, "recency": 0.10,
        "sample_size": 0.20, "parse_quality": 0.10,
    },
}
```

选择建议：

- 检验项目初筛阳性 → `early_diagnosis`（更看重新文献、新方法）
- 多指标联合鉴别 → `differential_diagnosis`（默认，平衡）
- 治疗随访评估 → `prognosis`（看重证据等级 + 大样本队列）

---

## Tier 分档

```
score >= 0.80 → S   必读 / 进 top-k 头部
score >= 0.60 → A   推荐
score >= 0.45 → B   参考
score <  0.45 → C   背景
```

`tier` 不直接决定是否保留，但供人工快速浏览时筛选。

---

## 踢出分类（仅 `filter_literature` 用）

5 维度打分不剔除任何论文。`literature_filter.filter_literature` 在打分基础上额外做 3 类踢出（用于快速缩小 top-k 候选池）：

| 踢出标签 | 触发条件 | 默认行为 |
|---------|---------|---------|
| `parse_failed` | abstract 为空 / 是作者列表 / 是占位符 | 踢出 |
| `offtopic` | topic_match = 0 且 evidence_level < 0.3 | 踢出 |
| `low_quality` | parse_quality < 0.4 | 踢出 |

踢出的论文仍保留在产物的 `kicked_summary` 字段，方便审计。

---

## Pipeline 集成

`pipeline/run.py` 步骤⑤之后、步骤⑥之前自动跑⑤b：

```
⑤ 文献检索       → literature_results.json (39 篇)
⑤b 文献证据打分   → literature_results.filtered.json (top-k = 8)
⑥ 循证解读        → 读 .filtered.json 做 LLM 解读
```

CLI 开关：

```bash
# 默认开启
python -m lab_analysis --skip-ingest --skip-imaging --skip-llm \
    --lit-filter-scenario differential_diagnosis \
    --lit-filter-top-k 8

# 跳过
python -m lab_analysis --skip-lit-filter
```

---

## 独立使用

### Python API

```python
from lab_analysis.evidence_grader import grade_paper, rank_papers

# 单篇打分
graded = grade_paper(
    paper={"pmid": "38714508", "title": "...", "abstract": "...", "year": "2024"},
    scenario="differential_diagnosis",
    topic="sepsis_gn_gp",
)
print(graded.score, graded.tier)
print(graded.reasons)   # 5 条解释

# 批量排序
ranked = rank_papers(papers, scenario="differential_diagnosis", top_k=8)
for g in ranked:
    print(f"[{g.tier}] {g.score:.3f}  PMID:{g.pmid}  {g.title[:80]}")
```

### CLI 入口

```bash
# 临时调试
python -m lab_analysis.evidence_grader \
    --in data/<deid>/<ts>/03_literature/literature_results.json \
    --scenario differential_diagnosis \
    --topic sepsis_gn_gp \
    --top-k 5

# Pipeline 模式（自动定位路径 + 输出）
ANALYSIS_TS=20260612_185152 python -m lab_analysis.literature_filter \
    --id-card 846552421134373347 --top-k 8
```

---

## 产物 Schema

```json
{
  "scenario": "differential_diagnosis",
  "topic": "sepsis_gn_gp",
  "total_papers": 39,
  "kept_papers": 8,
  "filtered_papers": [
    {
      "pmid": "38714508",
      "title": "...",
      "year": "2024",
      "abstract": "...",
      "grade": {
        "score": 0.955,
        "tier": "S",
        "scenario": "differential_diagnosis",
        "subscores": {
          "topic_match": 1.0,
          "evidence_level": 1.0,
          "recency": 0.85,
          "sample_size": 0.9,
          "parse_quality": 1.0
        },
        "reasons": [
          "主题匹配(0.30): sepsis + gram-negative + biomarker + ...",
          "证据等级(0.25): Meta-analysis (1.0)",
          ...
        ]
      }
    }
  ],
  "kicked_summary": {
    "parse_failed": [{"pmid": "...", "reason": "abstract 是作者列表"}],
    "offtopic": [{"pmid": "...", "reason": "topic_match=0"}],
    "low_quality": [{"pmid": "...", "reason": "parse_quality=0.2"}]
  }
}
```

---

## 测试覆盖

`tests/test_evidence_grader.py` 32 个用例：

- TestScoreTopicMatch（5）— 关键词命中、零命中、儿科、英文大小写
- TestScoreEvidenceLevel（4）— Meta/RCT/cohort/case report
- TestScoreRecency（4）— 当年/3年/8年/20年
- TestScoreSampleSize（3）— n=2000 / n=100 / 无 n
- TestScoreParseQuality（5）— 完整摘要/空/作者列表/占位符/正常
- TestTierFromScore（4）— S/A/B/C 边界
- TestGradePaper（3）— 完整打分校验
- TestRankPapers（2）— 排序 + top_k 截取
- TestScenarioWeights（1）— 三 scenario 权重求和=1
- TestEndToEnd（1）— 真实 10 篇 PubMed 文献端到端

```bash
python -m pytest tests/test_evidence_grader.py -v
# → 32 passed in 0.06s
```

---

## 限制

- 关键词库 `TOPIC_KEYWORDS` 当前仅覆盖 `sepsis_gn_gp` / `inflammation` / `rdw`，新增主题需扩库
- `sample_size` 维度依赖 abstract 正则提取，遇到非英文单位可能漏判
- 三种场景权重是经验值，未做大规模对照实验优化
- Tier 阈值（S/A/B/C = 0.80/0.60/0.45）按经验设，可按业务调整