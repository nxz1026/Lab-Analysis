# Vision 模块使用说明

## 功能概述

Vision 模块使用 OpenRouter API (Qwen-VL) 从检验报告图片中自动识别患者信息，包括：
- 患者ID（身份证号）
- 报告日期
- 报告类型（门诊/住院）

## 重要规则

### ⚠️ 患者ID验证规则

**患者ID必须是有效的中国大陆身份证号：**
- ✅ 18位：17位数字 + 1位数字或X（例如：`513229198801040014`）
- ✅ 15位：15位数字（旧版身份证）
- ❌ 其他格式均视为无效

**如果识别到的ID无效：**
1. **自动模式**（默认）：自动跳过该数据，记录错误原因
2. **交互模式**（`--interactive`）：提示用户选择
   - 选项1：手动输入正确的身份证号
   - 选项2：放弃此数据

---

## 使用方法

### 1. 单张图片识别

#### 自动模式（推荐用于批量处理）
```bash
cd e:\2026Workplace\Code\nxz1026\Lab-Analysis
.\.venv\Scripts\python.exe -m lab_analysis.vision_extractor \
    --image "C:\Users\ND\wiki\raw\Origin_data\lab_2026-03-24_outpatient.jpg" \
    --output "C:\Users\ND\wiki\raw\Origin_data\result.json"
```

#### 交互模式（需要人工确认）
```bash
.\.venv\Scripts\python.exe -m lab_analysis.vision_extractor \
    --image "C:\Users\ND\wiki\raw\Origin_data\lab_2026-04-08_inpatient.jpg" \
    --interactive
```

当识别到无效ID时，会提示：
```
⚠️  警告: 识别到的患者ID '0000270564' 不是有效的身份证号格式
   期望格式: 18位数字(最后一位可能是X) 或 15位数字

请选择操作:
  1. 手动输入正确的患者ID
  2. 放弃此数据

请输入选择 (1/2): 
```

### 2. 批量处理所有图片

#### 自动模式（默认）
```bash
cd e:\2026Workplace\Code\nxz1026\Lab-Analysis
.\.venv\Scripts\python.exe -m lab_analysis.batch_vision_extract
```

**行为：**
- 自动扫描 `C:\Users\ND\wiki\raw\Origin_data\` 下所有 `lab_*.jpg` 文件
- 识别每张图的患者信息
- 验证ID格式，无效的自动跳过
- 有效的自动调用 `ingest_image.py` 存入正确目录
- 生成汇总报告

#### 交互模式
```bash
.\.venv\Scripts\python.exe -m lab_analysis.batch_vision_extract --interactive
```

**行为：**
- 同上，但当遇到无效ID时会暂停，等待用户输入
- 用户可以选择手动输入正确的ID或放弃

---

## 输出示例

### 成功识别
```json
{
  "patient_id": "513229198801040014",
  "report_date": "2026-03-24",
  "report_type": "outpatient",
  "confidence": 0.95
}
```

### ID无效（自动模式）
```json
{
  "patient_id": null,
  "report_date": "2026-04-08",
  "report_type": "outpatient",
  "confidence": 0.9,
  "error": "识别的ID \"0000270564\" 不是有效的身份证号"
}
```

### ID无效（交互模式 - 用户放弃）
```json
{
  "patient_id": null,
  "report_date": "2026-04-08",
  "report_type": "outpatient",
  "confidence": 0.0,
  "error": "用户放弃"
}
```

### ID无效（交互模式 - 用户手动输入）
```json
{
  "patient_id": "510123199001011234",
  "report_date": "2026-04-08",
  "report_type": "outpatient",
  "confidence": 1.0,
  "note": "用户手动修正"
}
```

---

## API 配置

OpenRouter API Key 存储在：`C:\Users\ND\.hermes\.env`

```env
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
```

使用的模型：`qwen/qwen-vl-plus`

---

## 常见问题

### Q1: 为什么有些ID被标记为无效？
A: 因为患者ID必须是18位或15位的身份证号。如果OCR识别出来的是病历号、诊疗卡号等其他编号（如 `0000270564`），会被判定为无效。

### Q2: 如何处理识别错误的情况？
A: 使用 `--interactive` 模式，可以手动输入正确的身份证号。

### Q3: 批量处理时如何知道哪些图片被跳过了？
A: 查看生成的汇总报告：`C:\Users\ND\wiki\raw\Origin_data\batch_extraction_summary.json`

### Q4: 能否修改ID验证规则？
A: 可以修改 `vision_extractor.py` 中的 `validate_chinese_id()` 函数，但建议保持身份证号验证以确保数据一致性。

---

## 工作流程

```
原始图片 (Origin_data/)
    ↓
Vision 识别 (Qwen-VL via OpenRouter)
    ↓
提取患者ID、日期、类型
    ↓
验证ID格式 (18位或15位身份证号)
    ↓
    ├─ 有效 → 调用 ingest_image.py → 存入 raw/patient_{脱敏ID}/lab/
    │
    └─ 无效 → 
         ├─ 自动模式：跳过，记录错误
         └─ 交互模式：提示用户输入或放弃
```

---

## 下一步

数据成功存入后，可以运行完整的分析流程：

```bash
cd e:\2026Workplace\Code\nxz1026\Lab-Analysis
.\.venv\Scripts\python.exe -m lab_analysis.pipeline --patient-id <患者ID>
```

例如：
```bash
.\.venv\Scripts\python.exe -m lab_analysis.pipeline --patient-id 513229198801040014
```
