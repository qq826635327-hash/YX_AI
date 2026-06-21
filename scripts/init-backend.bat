@echo off
chcp 65001 >nul
REM 初始化后端环境（首次使用执行）
set ROOT=%~dp0..
cd /d %ROOT\backend

echo [1/3] 创建 Python 虚拟环境...
C:\Users\82663\.workbuddy\binaries\python\versions\3.13.12\python.exe -m venv .venv

echo [2/3] 升级 pip...
.venv\Scripts\python.exe -m pip install --upgrade pip

echo [3/3] 安装后端依赖...
.venv\Scripts\pip install -e .

echo.
echo 后端环境初始化完成！
pause
