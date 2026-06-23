# README 中英对齐基线 (2026-06-23)

## 概览

| 文件 | 章节数 | 大小 |
|------|------|------|
| README.md (中) | 45 | ~28 KB |
| README_en.md (英) | 34 | ~16 KB |

## 缺口

- **英文版需补充 45 项**: 中文版有但英文版无 (主要为新增功能说明)
- **中文版需补充 34 项**: 英文版有但中文版无 (主要为安装/环境变量细节)

## 自动化

`scripts/check_readme_alignment.py` 已就位：
- 默认模式：报告两版差异清单
- `--check` 模式：缺失则 exit 1，可接入 CI

## 后续补写计划 (P1-4 baseline 完成后)

按优先级：

1. **英文版补写 (高优)**: 增量同步中文版新增内容
   - 新增 `适用场景` / `核心特性` 概述
   - 新增 `MCP Server 集成` 章节
   - 新增 `数据清理` / `FHIR Export` / `Lab Metric Prediction` 章节
2. **中文版补写 (中优)**: 同步英文版细节
   - `Requirements` / `Environment Variables` 详细表
   - `Skip Steps` / `Debug a Single Step` 用法

## 触发机制

pre-commit hook 已配置 (stages: manual)：
```bash
pre-commit run check-readme-alignment --all-files
```

baseline 阶段不阻塞，缺口修复后可改为强制 (--check 模式 + 接入 CI gate)。