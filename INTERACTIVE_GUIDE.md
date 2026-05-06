# 交互式 Vision 识别操作指南

## 📋 前置说明

由于后台运行的程序无法接收键盘输入，你需要在**前台 PowerShell 窗口**中手动运行交互式命令。

---

## 🚀 操作步骤

### 步骤1：打开新的 PowerShell 窗口

按 `Win + R`，输入 `powershell`，按回车。

### 步骤2：进入项目目录

```powershell
cd e:\2026Workplace\Code\nxz1026\Lab-Analysis
```

### 步骤3：运行交互式识别命令

#### 处理第一张有问题的图片（lab_2026-04-08_inpatient.jpg）

```powershell
.\.venv\Scripts\python.exe -m lab_analysis.vision_extractor --image "C:\Users\ND\wiki\raw\Origin_data\lab_2026-04-08_inpatient.jpg" --interactive
```

**等待程序输出，你会看到类似以下内容：**

```
[Vision] 正在分析图片: lab_2026-04-08_inpatient.jpg
[Vision] 调用 Qwen-VL API...

[WARNING] 识别到的患者ID '0000270564' 不是有效的身份证号格式
   期望格式: 18位数字(最后一位可能是X) 或 15位数字

请选择操作:
  1. 手动输入正确的患者ID
  2. 放弃此数据

请输入选择 (1/2): 
```

**此时你有两个选择：**

#### 选项A：手动输入正确的身份证号

1. 输入 `1`，按回车
2. 程序会提示：`请输入患者身份证号: `
3. 输入正确的18位身份证号（例如：`510123199001011234`），按回车
4. 如果格式正确，会显示：`[OK] 已更新患者ID: xxxxx`
5. 数据会自动存入正确目录

#### 选项B：放弃此数据

1. 输入 `2`，按回车
2. 程序会显示：`[INFO] 用户选择放弃此数据`
3. 跳过这张图片

---

### 步骤4：处理第二张图片（lab_2026-04-14_inpatient.jpg）

同样的命令，替换图片路径：

```powershell
.\.venv\Scripts\python.exe -m lab_analysis.vision_extractor --image "C:\Users\ND\wiki\raw\Origin_data\lab_2026-04-14_inpatient.jpg" --interactive
```

重复步骤3的操作。

---

## ✅ 验证结果

处理完成后，检查数据是否成功存入：

```powershell
# 查看已存入的患者目录
Get-ChildItem "C:\Users\ND\wiki\raw" -Directory | Select-Object Name
```

你应该能看到类似：
- `patient_846552421134373347` （患者 513229198801040014）
- `patient_xxxxxxxxxxxxxxxx` （如果你手动输入了其他ID）

---

## 🎯 下一步：运行完整 Pipeline

当所有数据处理完成后，运行完整分析流程：

```powershell
cd e:\2026Workplace\Code\nxz1026\Lab-Analysis
.\.venv\Scripts\python.exe -m lab_analysis.pipeline --patient-id 513229198801040014
```

---

## ❓ 常见问题

### Q1: 我不知道正确的身份证号怎么办？
A: 你可以：
- 查看原始检验报告图片，找到正确的诊疗卡号/身份证号
- 或者选择选项2放弃此数据
- 或者联系数据提供方获取正确信息

### Q2: 输入的身份证号格式错误怎么办？
A: 程序会提示 `[ERROR] 输入的ID格式无效，放弃此数据`，然后你可以重新运行命令再次尝试。

### Q3: 如何确认身份证号格式是否正确？
A: 中国大陆身份证号规则：
- 18位：17位数字 + 1位数字或X（例如：`513229198801040014`）
- 15位：15位数字（旧版，例如：`513229880104014`）

### Q4: 能否批量自动处理？
A: 可以，使用自动模式（不添加 `--interactive` 参数）：
```powershell
.\.venv\Scripts\python.exe -m lab_analysis.batch_vision_extract
```
无效ID的图片会自动跳过。

---

## 📞 需要帮助？

如果在操作过程中遇到问题，请告诉我：
1. 你看到了什么错误信息
2. 你想如何处理这些图片

我会为你提供进一步的指导！
