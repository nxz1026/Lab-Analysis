# 测试环境搭建指南

## ✅ 已完成的工作

1. ✅ 创建了 `.hermes` 配置目录
2. ✅ 创建了 `wiki/raw` 和 `wiki/data` 目录
3. ✅ 生成了 `.env` 配置文件模板
4. ✅ 生成了 `patient_info.json` 患者信息模板
5. ✅ 创建了环境验证脚本 `test_env.ps1`

## 📋 下一步操作

### 1️⃣ 配置 API 密钥

编辑文件：`C:\Users\ND\.hermes\.env`

将占位符替换为你的真实 API 密钥：

```env
# DeepSeek API 密钥
DEEPSEEK_API_KEY=sk-你的真实密钥

# 阿里云 DashScope API 密钥
DASHSCOPE_API_KEY=sk-你的真实密钥
```

### 2️⃣ 准备原始数据

你需要将原始数据放入以下目录结构：

```
C:\Users\ND\wiki\raw\patient_<患者ID>\
├── papers\
│   ├── lab_report_001\
│   │   ├── metadata.md      # 报告元数据
│   │   └── metrics.md       # 检验指标（YAML格式）
│   ├── lab_report_002\
│   │   ├── metadata.md
│   │   └── metrics.md
│   └── ...
└── imaging\                  # 可选，MRI影像文件
    ├── seq_01\
    │   └── *.dcm
    └── ...
```

**注意：** 患者ID是程序从 Vision 模块自动读取的，请确认你的 Vision 模块输出的 ID 是什么。

### 3️⃣ 安装 Python 依赖

在项目根目录执行：

```powershell
cd e:\2026Workplace\Code\nxz1026\Lab-Analysis

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
.venv\Scripts\activate

# 升级 pip
python -m pip install --upgrade pip

# 安装项目依赖（包含 pydicom）
pip install -e .
```

### 4️⃣ 运行测试

#### 方式一：完整流程测试

```powershell
python run_analysis.py --patient-id <你的患者ID>
```

#### 方式二：单步测试（推荐先这样）

```powershell
# 第1步：数据加载
python -m lab_analysis.data_loader --patient-id <患者ID>

# 第2步：数据分析
python -m lab_analysis.data_analyzer --patient-id <患者ID>

# 第3步：文献检索
python -m lab_analysis.literature_searcher --topic "chronic pancreatitis" --n 5 --patient-id <患者ID>

# 第4步：文献解读（需要API密钥）
python -m lab_analysis.literature_interpreter --patient-id <患者ID>

# 第5步：跳过影像，生成报告
python -m lab_analysis.gen_final_report --patient-id <患者ID>
```

## 🔍 验证环境

随时可以运行验证脚本检查环境状态：

```powershell
.\test_env.ps1
```

## 📝 数据文件格式示例

### metadata.md 示例

```markdown
| 字段 | 值 |
|------|-----|
| 报告日期 | 2026-04-14 |
| 科室 | 消化内科 |
| 医生 | 张医生 |
| 诊断 | 慢性胰腺炎 |
| 报告类型 | 住院 |
```

### metrics.md 示例

```yaml
metrics:
  - date: "2026-04-14"
    hsCRP: 5.2
    CRP: 12.5
    WBC: 8.5
    RBC: 4.5
    HGB: 140
    HCT: 42
    PLT: 250
    # ... 其他指标
```

## ❓ 常见问题

### Q: 患者ID从哪里来？
A: 根据你的描述，ID是从 Vision 模块自动读取的。请确认：
- Vision 模块的输出在哪里？
- 输出的 ID 格式是什么？
- 是否需要手动指定第一个测试的 ID？

### Q: 没有影像数据怎么办？
A: 可以使用 `--skip-imaging` 参数跳过影像分析步骤。

### Q: API 调用失败怎么办？
A: 检查：
1. `.env` 文件中的密钥是否正确
2. 网络连接是否正常
3. API 配额是否充足

## 🎯 快速开始 Checklist

- [ ] 编辑 `.env` 文件，填入真实 API 密钥
- [ ] 将原始数据放入 `wiki/raw/patient_<ID>/` 目录
- [ ] 运行 `python -m venv .venv`
- [ ] 运行 `.venv\Scripts\activate`
- [ ] 运行 `pip install -e .`
- [ ] 运行 `python run_analysis.py --patient-id <ID>` 测试

---

**准备好了吗？告诉我你的患者ID，我们就可以开始测试了！** 🚀
