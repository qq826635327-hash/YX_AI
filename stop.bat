@echo off
chcp 65001 >nul

REM ============================================================
REM  AI Drama Studio - 一键停止脚本
REM  位置：项目根目录 D:\影序AI\stop.bat
REM  用法：双击运行，或命令行执行 stop.bat
REM ============================================================

echo.
echo  正在停止 AI Drama Studio 服务...
echo.

set "FOUND=0"

REM 停止后端（uvicorn 进程）
for /f "tokens=2" %%a in ('tasklist /fi "WINDOWTITLE eq ADS-Backend*" /fo list 2^>nul ^| findstr "PID:"') do (
    taskkill /PID %%a /T /F >nul 2>&1
    set "FOUND=1"
    echo   [ok] 后端已停止
)

REM 停止前端（vite 进程）
for /f "tokens=2" %%a in ('tasklist /fi "WINDOWTITLE eq ADS-Frontend*" /fo list 2^>nul ^| findstr "PID:"') do (
    taskkill /PID %%a /T /F >nul 2>&1
    set "FOUND=1"
    echo   [ok] 前端已停止
)

REM 备用方案：按端口查找并停止
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
    set "FOUND=1"
    echo   [ok] 端口 8000 进程已停止
)

for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
    set "FOUND=1"
    echo   [ok] 端口 5173 进程已停止
)

if "%FOUND%"=="0" (
    echo   [i] 未发现运行中的服务
)

echo.
echo  所有服务已停止。
echo.
