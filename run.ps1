# ============================================================================
# Lab-Analysis Pipeline 启动脚本 (PowerShell 版, 完整 UTF-8 支持)
# ============================================================================
# 优势 (相比 run.bat):
#   - 自动加载 $PROFILE (chcp 65001, PYTHONUTF8, PYTHONIOENCODING)
#   - 实时彩色输出
#   - 更好的错误处理
#   - 跨平台兼容 (PowerShell Core)
#
# 用法:
#   .\run.ps1                                          # 交互模式
#   .\run.ps1 -PatientId "513229198801040014"          # 指定患者
#   .\run.ps1 -PatientId "xxx" -UseDspy                # DSPy 模式
#   .\run.ps1 -NoInteractive -UseDspy                  # 静默 + DSPy
# ============================================================================

[CmdletBinding()]
param(
    [string]$PatientId,
    [switch]$UseDspy,
    [switch]$NoInteractive,
    [switch]$UploadToFeishu,
    [switch]$Help
)

# 颜色输出函数
function Write-Step($msg) { Write-Host "[STEP] $msg" -ForegroundColor Cyan }
function Write-OK($msg)    { Write-Host "[OK]    $msg" -ForegroundColor Green }
function Write-Fail($msg)  { Write-Host "[FAIL]  $msg" -ForegroundColor Red }
function Write-Warn($msg)  { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }

if ($Help) {
    Get-Help $PSCommandPath
    exit 0
}

# 1. 加载 PowerShell profile (UTF-8 配置)
if (Test-Path $PROFILE) {
    . $PROFILE
    Write-OK "Profile loaded: UTF-8 mode"
} else {
    Write-Warn "Profile not found, switching to UTF-8 manually"
    chcp 65001 | Out-Null
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"
}

# 2. 设置 Python UTF-8 环境变量
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONLEGACYWINDOWSSTDIO = "0"
$env:PYTHONUNBUFFERED = "1"
$env:LANG = "zh_CN.UTF-8"
$env:LC_ALL = "zh_CN.UTF-8"

# 3. 定位 venv
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $ScriptDir "..\.venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Fail "找不到虚拟环境: $VenvPython"
    Write-Warn "请先创建 .venv: python -m venv ..\.venv"
    exit 1
}

# 4. 切换到脚本目录
Push-Location $ScriptDir

# 5. 显示配置
Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host "  Lab-Analysis Pipeline (PowerShell UTF-8 模式)" -ForegroundColor Cyan
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Step "Python:    $VenvPython"
Write-Step "CodePage:  $(([Console]::OutputEncoding.CodePage)) (UTF-8)"
Write-Step "PYTHONUTF8: $($env:PYTHONUTF8)"
Write-Step "工作目录:  $ScriptDir"
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""

# 6. 构建参数列表
$pythonArgs = @("-X", "utf8", "$ScriptDir\run_analysis.py")
if ($PatientId)        { $pythonArgs += @("--patient-id", $PatientId) }
if ($UseDspy)          { $pythonArgs += @("--use-dspy") }
if ($NoInteractive)    { $pythonArgs += @("--no-interactive") }
if ($UploadToFeishu)   { $pythonArgs += @("--upload-to-feishu") }

# 7. 启动 Python
Write-Step "启动: & python $pythonArgs"
& python.exe @pythonArgs
$exitCode = $LASTEXITCODE

# 8. 退出处理
Pop-Location
if ($exitCode -ne 0) {
    Write-Host ""
    Write-Fail "Pipeline 退出码: $exitCode"
    exit $exitCode
}
Write-Host ""
Write-OK "Pipeline 执行完毕"
exit 0
