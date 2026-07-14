@echo off
chcp 65001 >nul
title TalentScope 离线版

cd /d "%~dp0"

set "PROJECT_PY=.venv\Scripts\python.exe"
set "APP_FILE=src\talentscope\ui\app.py"
set "REQ_FILE=requirements.txt"

echo.
echo ============================================================
echo   TalentScope - 离线独立运行版
echo ============================================================
echo.

if not exist "%APP_FILE%" (
    echo [X] 未找到应用入口文件：%APP_FILE%
    echo.
    echo 请确认 src 目录是否完整，或重新执行离线打包。
    pause
    exit /b 1
)

if not exist "%PROJECT_PY%" (
    echo [i] 未检测到项目虚拟环境，准备自动创建 .venv
    echo.

    py -3.11 -m venv .venv >nul 2>nul
    if errorlevel 1 (
        py -3 -m venv .venv >nul 2>nul
    )
    if errorlevel 1 (
        python -m venv .venv >nul 2>nul
    )

    if not exist "%PROJECT_PY%" (
        echo [i] 当前系统未检测到可用 Python，尝试联网自动安装 Python 3.11 ...
        winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements >nul 2>nul

        py -3.11 -m venv .venv >nul 2>nul
        if errorlevel 1 (
            python -m venv .venv >nul 2>nul
        )
    )

    if not exist "%PROJECT_PY%" (
        echo [X] 自动安装/配置 Python 失败。
        echo.
        echo 请手动安装 Python 3.10+ 后重试：
        echo https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
)

echo [+] 使用解释器：%PROJECT_PY%

"%PROJECT_PY%" -m pip --version >nul 2>nul
if errorlevel 1 (
    echo [i] 正在初始化 pip ...
    "%PROJECT_PY%" -m ensurepip --upgrade >nul 2>nul
)

"%PROJECT_PY%" -c "import streamlit, pandas" >nul 2>nul
if errorlevel 1 (
    if exist "%REQ_FILE%" (
        echo [i] 首次运行或依赖缺失，正在自动安装依赖，请稍候...
        "%PROJECT_PY%" -m pip install --upgrade pip
        "%PROJECT_PY%" -m pip install -r "%REQ_FILE%"
        if errorlevel 1 (
            echo [X] 依赖安装失败，请检查网络后重试。
            pause
            exit /b 1
        )
    ) else (
        echo [X] 未找到依赖文件：%REQ_FILE%
        pause
        exit /b 1
    )
)

echo [+] 环境检查完成。

echo [+] 正在启动服务...
echo [i] 浏览器将自动打开 http://localhost:8501
echo [i] 关闭本窗口即可停止服务
echo.

"%PROJECT_PY%" -m streamlit run "%APP_FILE%" --server.headless false --server.port 8501 --browser.gatherUsageStats false

pause
