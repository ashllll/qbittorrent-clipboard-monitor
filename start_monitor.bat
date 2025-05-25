@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo.
echo ==========================================
echo QBittorrent智能下载助手启动脚本
echo ==========================================
echo.

set "VENV_DIR=venv"
set "PYTHON_EXE=python"

echo [1/8] 检查Python环境...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo 成功: 找到Python %PYTHON_VERSION%

echo [2/8] 检查虚拟环境...
if not exist "%VENV_DIR%" (
    echo 创建虚拟环境...
    python -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo 错误: 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo 成功: 虚拟环境创建完成
) else (
    echo 成功: 虚拟环境已存在
)

echo [3/8] 激活虚拟环境...
if exist "%VENV_DIR%\Scripts\activate.bat" (
    call "%VENV_DIR%\Scripts\activate.bat"
    echo 成功: 虚拟环境已激活
) else (
    echo 错误: 找不到虚拟环境激活脚本
    pause
    exit /b 1
)

echo [4/8] 升级pip...
python -m pip install --upgrade pip --quiet
if %errorlevel% equ 0 (
    echo 成功: pip已升级
) else (
    echo 警告: pip升级失败，继续...
)

echo [5/8] 检查依赖包...
if exist "requirements.txt" (
    echo 安装依赖包...
    python -m pip install -r requirements.txt --quiet
    if %errorlevel% neq 0 (
        echo 错误: 安装依赖失败，尝试详细安装...
        python -m pip install -r requirements.txt
        if %errorlevel% neq 0 (
            echo 错误: 依赖安装失败
            pause
            exit /b 1
        )
    )
    echo 成功: 依赖安装完成
) else (
    echo 警告: 未找到requirements.txt，安装基础依赖...
    python -m pip install aiohttp pyperclip --quiet
)

echo [6/8] 检查配置文件...
if not exist "qbittorrent_monitor\config.json" (
    echo 错误: 配置文件不存在
    echo 请确保存在文件: qbittorrent_monitor\config.json
    pause
    exit /b 1
)
echo 成功: 配置文件检查完成

echo [7/8] 准备启动...
echo.
echo ==========================================
echo 启动信息:
echo 虚拟环境: %VENV_DIR%
echo 配置文件: qbittorrent_monitor\config.json
echo 启动方式: python start.py
echo ==========================================
echo.

echo [8/8] 启动程序...
python start.py

echo.
echo 程序已退出，按任意键关闭窗口...
pause >nul 