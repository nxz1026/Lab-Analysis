# 飞书上传脚本备份说明

## 📁 文件说明

### 当前版本
- **文件**: `upload_to_feishu.py`
- **状态**: 正在开发中，使用 lark-cli 实现自动上传
- **功能**: 
  - ✅ 本地文件组织（完全正常）
  - 🔄 飞书自动上传（调试中）

### 备份版本
- **文件**: `upload_to_feishu_backup.py`
- **创建时间**: 2026-05-07
- **状态**: 稳定版本备份
- **用途**: 作为参考和回滚点

---

## 🔧 当前实现特点

### 1. 本地文件组织（✅ 已完善）

**目录结构：**
```
F:\Lab_analysis\local_upload\
└── {YYYY-MM-DD}/              # 当天日期文件夹
    ├── 原始数据/               # lab_metrics.csv/json
    ├── 文献参考/               # literature_results.md
    ├── 中间结果/               # interpretation + reports
    ├── 统计结果/               # 7张图表 (fig_01~07)
    └── final_integrated_report.md  # 综合报告（根目录）
```

**使用方法：**
```bash
python -m lab_analysis.upload_to_feishu --patient-id YOUR_ID
```

**输出：**
- ✅ 13个文件成功复制
- ⚠️ 1个文件跳过（MRI报告，未执行MRI分析）

---

### 2. 飞书自动上传（🔄 调试中）

**技术方案：** 使用 lark-cli 命令行工具

**核心命令：**
```bash
# 检查/列出文件夹
lark-cli drive files list --params '{"folder_token": "xxx", "page_size": 50}'

# 创建文件夹
lark-cli drive +create-folder --name "文件夹名" --folder-token "父token"

# 上传文件（cp → upload → rm）
cp "源文件" "./临时文件"
lark-cli drive +upload --file ./临时文件 --folder-token "目标token"
rm ./临时文件
```

**配置要求：**
1. 安装 lark-cli: `npm install -g @larksuiteoapi/lark-cli`
2. 配置环境变量: `FEISHU_FOLDER_TOKEN=xxx`

**使用方法：**
```bash
python -m lab_analysis.upload_to_feishu --patient-id YOUR_ID --upload-to-feishu
```

**当前问题：**
- ⚠️ Windows 编码问题（GBK vs UTF-8）
- ⚠️ lark-cli 输出解析问题
- 💡 建议：暂时使用本地文件组织 + 手动上传

---

## 📊 版本对比

| 特性 | 备份版本 | 当前版本 |
|------|---------|---------|
| 本地文件组织 | ✅ | ✅ |
| 飞书API集成 | ❌ | ✅ (调试中) |
| lark-cli支持 | ❌ | ✅ |
| Windows兼容 | N/A | 🔄 (部分) |
| 错误处理 | 基础 | 完善 |
| 代码行数 | ~170行 | ~520行 |

---

## 🎯 使用建议

### 方案1：稳定方案（推荐）
```bash
# 1. 执行本地文件组织
python -m lab_analysis.upload_to_feishu --patient-id YOUR_ID

# 2. 手动上传到飞书
# 打开 F:\Lab_analysis\local_upload\2026-05-07
# 拖拽整个文件夹到飞书云盘
```

**优点：**
- ✅ 稳定可靠
- ✅ 无需配置
- ✅ 可检查结果后再上传

### 方案2：自动化方案（待完善）
```bash
# 等待编码问题和API解析问题解决后
python -m lab_analysis.upload_to_feishu --patient-id YOUR_ID --upload-to-feishu
```

**优点：**
- 🚀 全自动流程
- 🚀 一键完成

**缺点：**
- ⚠️ 需要配置 lark-cli
- ⚠️ 目前仍有bug

---

## 📝 开发历史

### 2026-05-07
- ✅ 创建初始版本（纯本地文件组织）
- ✅ 集成 lark-cli 支持
- ✅ 添加 Windows 兼容性（shell=True）
- ✅ 改进错误处理和调试信息
- 🔄 修复编码问题和命令格式
- 💾 创建备份文件

---

## 🔗 相关文件

- **主脚本**: `lab_analysis/upload_to_feishu.py`
- **备份脚本**: `lab_analysis/upload_to_feishu_backup.py`
- **环境变量**: `.env` (包含 FEISHU_FOLDER_TOKEN)
- **Git忽略**: `.gitignore` (忽略 *_backup.py)

---

## 💡 注意事项

1. **备份文件不会被提交到Git**
   - 已在 `.gitignore` 中配置 `*_backup.py`
   - 仅作为本地开发参考

2. **敏感信息保护**
   - `.env` 文件不会被提交
   - FEISHU_FOLDER_TOKEN 等凭证保存在本地

3. **回滚方法**
   ```bash
   # 如果当前版本有问题，可以恢复备份
   Copy-Item lab_analysis\upload_to_feishu_backup.py lab_analysis\upload_to_feishu.py
   ```

---

**最后更新**: 2026-05-07  
**维护者**: Lab-Analysis Team
