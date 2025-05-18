@echo off
setlocal enabledelayedexpansion

echo 检查并安装日志高亮工具的依赖项...

set "libs_dir=libs"
set "requirements_file=requirements.txt"

if not exist "%libs_dir%" (
    echo 创建 libs 目录...
    mkdir "%libs_dir%"
)

if not exist "%requirements_file%" (
    echo 创建 requirements.txt 文件...
    (
        echo brotli
        echo easyprocess
        echo entrypoint2
        echo patoolib
        echo psutil
        echo py7zr
        echo PyQt5
        echo PyQt5-Qt5
        echo PyQt5-sip
        echo pyunpack
        echo pyzstd
        echo rarfile
        echo setuptools
        echo setuptools-scm
    ) > "%requirements_file%"
)

echo 检查并下载缺失的依赖项到 libs 目录...
for /f "tokens=*" %%i in (%requirements_file%) do (
    set "package=%%i"
    set "package=!package:-=_!"
    set "found=false"
    for %%f in ("%libs_dir%\!package!*.whl") do (
        set "found=true"
    )
    if "!found!"=="false" (
        echo 下载 !package!...
        pip download !package! -d "%libs_dir%" --no-deps
    ) else (
        echo !package! 已经存在，跳过下载。
    )
)

echo 安装依赖项...
pip install -r "%requirements_file%" --no-index --find-links="%libs_dir%"

echo 依赖项检查和安装完成。
pause