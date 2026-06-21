@echo off
chcp 65001 >nul
REM 初始化前端环境（首次使用执行）
set ROOT=%~dp0..
cd /d %ROOT\frontend

echo 安装前端依赖...
npm install --no-audit --no-fund

echo.
echo 前端环境初始化完成！
pause
