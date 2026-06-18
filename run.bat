@echo off
REM ============================================================================
REM Lab-Analysis Pipeline 启动脚本 (UTF-8 中文显示修复版)
REM ============================================================================
REM 作用:
REM   1. 切换控制台到 UTF-8 代码页 (65001)
REM   2. 设置 Python UTF-8 环境变量
REM   3. 激活项目 .venv
REM   4. 调用 run_analysis.py
REM
REM 用法:
REM   run.bat                                          # 交互模式（运行时输入身份证号）
REM   run.bat --use-dspy                               # DSPy 模式
REM   run.bat --no-interactive --use-dspy               # 静默 + DSPy
REM ============================================================================

REM 1. 切换到 UTF-8 代码页
chcp 65001 > nul

REM 2. 启用延迟扩展 (用于显示中文变量)
setlocal EnableDelayedExpansion

REM 3. 设置 Python UTF-8 环境变量
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "PYTHONLEGACYWINDOWSSTDIO=0"
set "PYTHONUNBUFFERED=1"
set "LANG=zh_CN.UTF-8"
set "LC_ALL=zh_CN.UTF-8"

REM 4. 切换到脚本所在目录 (项目根)
pushd "%~dp0"

REM 5. 激活 .venv (Code 根目录)
set "VENV_PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%VENV_PYTHON%" (
    echo [FAIL] 找不到虚拟环境: %VENV_PYTHON%
    echo [TIP]  请先创建 .venv: python -m venv ..\.venv
    popd
    exit /b 1
)

REM 6. 显示配置信息
echo.
echo ============================================================
echo  Lab-Analysis Pipeline (UTF-8 模式)
echo ============================================================
echo  Python:    %VENV_PYTHON%
echo  CodePage:  65001 (UTF-8)
echo  PYTHONUTF8: %PYTHONUTF8%
echo  工作目录:   %CD%
echo ============================================================
echo.

REM 7. 启动 Python 脚本
"%VENV_PYTHON%" -X utf8 "%~dp0run_analysis.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

REM 8. 退出处理
popd
endlocal
if %EXIT_CODE% NEQ 0 (
    echo.
    echo [FAIL] Pipeline 退出码: %EXIT_CODE%
    exit /b %EXIT_CODE%
)
echo.
echo [OK] Pipeline 执行完毕
exit /b 0
