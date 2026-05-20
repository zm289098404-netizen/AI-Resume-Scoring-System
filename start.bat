@echo off
chcp 65001 >nul
title TalentScope - AI 简历智能筛选系统

cd /d "%~dp0"

echo.
echo  ============================================================
echo    TalentScope - AI 简历智能匹配评分系统
echo    博彦科技 2026 AI 大奖参赛项目
echo  ============================================================
echo.

REM ---- 1. 检查 Python ----
where python >nul 2>nul
if errorlevel 1 (
    echo [X] 未检测到 Python
    echo.
    echo 请先安装 Python 3.10+ : https://www.python.org/downloads/
    echo 安装时务必勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

REM ---- 2. 跑 bootstrap (环境检查 + 依赖安装 + 向导) ----
python bootstrap.py
if errorlevel 1 (
    echo.
    echo [X] 初始化失败，请查看上方错误信息
    pause
    exit /b 1
)

REM ---- 3. 启动 UI ----
echo.
echo  [+] 正在启动 Web 控制台...
echo  [i] 浏览器将自动打开 http://localhost:8501
echo  [i] 关闭此窗口即可停止服务
echo.

python -m streamlit run src\talentscope\ui\app.py --server.headless false --server.port 8501 --browser.gatherUsageStats false

pause
