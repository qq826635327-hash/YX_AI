@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

REM ============================================================
REM  AI Drama Studio - 一键启动脚本
REM  位置：项目根目录 D:\影序AI\start.bat
REM  用法：双击运行，或命令行执行 start.bat
REM  功能：环境检查 → 启动后端 → 健康验证 → 启动前端 → 就绪提示
REM ============================================================

set "ROOT=%~dp0"
set "BACKEND_PORT=8000"
set "FRONTEND_PORT=5173"

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║     AI Drama Studio - 一键启动              ║
echo  ╚══════════════════════════════════════════════╝
echo.

REM ============================================================
REM  1. 环境检查
REM ============================================================
echo [1/5] 检查运行环境...

REM 检查 Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [X] 未找到 Python，请先安装 Python 3.11+
    echo       下载: https://www.python.org/downloads/
    goto :error_exit
)
echo   [ok] Python 已安装

REM 检查 Node.js
where node >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   [X] 未找到 Node.js，请先安装 Node.js 18+
    echo       下载: https://nodejs.org/
    goto :error_exit
)
echo   [ok] Node.js 已安装

REM 检查后端虚拟环境
if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
    echo   [X] 后端虚拟环境不存在: backend\.venv\
    echo       请先运行: scripts\init-backend.bat
    goto :error_exit
)
echo   [ok] 后端虚拟环境已就绪

REM 检查前端依赖
if not exist "%ROOT%frontend\node_modules" (
    echo   [!] 前端依赖未安装，正在执行 npm install...
    pushd "%ROOT%frontend"
    call npm install --silent
    popd
    if !ERRORLEVEL! neq 0 (
        echo   [X] npm install 失败，请检查 Node.js 环境
        goto :error_exit
    )
)
echo   [ok] 前端依赖已就绪

REM ============================================================
REM  2. 端口检查
REM ============================================================
echo.
echo [2/5] 检查端口占用...

netstat -ano | findstr ":%BACKEND_PORT% " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo   [!] 端口 %BACKEND_PORT% 已被占用，尝试释放...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%BACKEND_PORT% " ^| findstr "LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
    netstat -ano | findstr ":%BACKEND_PORT% " | findstr "LISTENING" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo   [X] 端口 %BACKEND_PORT% 仍被占用，请手动关闭占用进程
        goto :error_exit
    )
    echo   [ok] 端口 %BACKEND_PORT% 已释放
) else (
    echo   [ok] 端口 %BACKEND_PORT% 可用
)

netstat -ano | findstr ":%FRONTEND_PORT% " | findstr "LISTENING" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo   [!] 端口 %FRONTEND_PORT% 已被占用，尝试释放...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%FRONTEND_PORT% " ^| findstr "LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
    echo   [ok] 端口 %FRONTEND_PORT% 已释放
) else (
    echo   [ok] 端口 %FRONTEND_PORT% 可用
)

REM ============================================================
REM  3. 启动后端
REM ============================================================
echo.
echo [3/5] 启动后端 FastAPI (http://127.0.0.1:%BACKEND_PORT%)...

start "ADS-Backend" /min cmd /c "title ADS-Backend && cd /d "%ROOT%backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port %BACKEND_PORT% && echo. && echo [后端已停止] && pause"

REM 等待后端就绪（最多 15 秒）
echo   等待后端启动...
set "BACKEND_READY=0"
for /L %%i in (1,1,15) do (
    if !BACKEND_READY! equ 0 (
        timeout /t 1 /nobreak >nul
        curl -s http://127.0.0.1:%BACKEND_PORT%/api/health >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            set "BACKEND_READY=1"
            echo   [ok] 后端已就绪 (%%i 秒^)
        )
    )
)

if %BACKEND_READY% equ 0 (
    echo   [!] 后端启动较慢，前端将继续启动...
    echo       请稍后手动访问 http://127.0.0.1:%BACKEND_PORT%/api/health 验证
)

REM ============================================================
REM  4. 启动前端
REM ============================================================
echo.
echo [4/5] 启动前端 Vite (http://127.0.0.1:%FRONTEND_PORT%)...

start "ADS-Frontend" /min cmd /c "title ADS-Frontend && cd /d "%ROOT%frontend" && npx vite --host 127.0.0.1 && echo. && echo [前端已停止] && pause"

REM 等待前端就绪（最多 10 秒）
echo   等待前端启动...
set "FRONTEND_READY=0"
for /L %%i in (1,1,10) do (
    if !FRONTEND_READY! equ 0 (
        timeout /t 1 /nobreak >nul
        curl -s -o nul http://127.0.0.1:%FRONTEND_PORT%/ >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            set "FRONTEND_READY=1"
            echo   [ok] 前端已就绪 (%%i 秒^)
        )
    )
)

if %FRONTEND_READY% equ 0 (
    echo   [!] 前端启动较慢，请稍后手动访问验证
)

REM ============================================================
REM  5. 就绪提示
REM ============================================================
echo.
echo [5/5] 启动结果
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║                                              ║
echo  ║   前端:  http://127.0.0.1:%FRONTEND_PORT%             ║
echo  ║   后端:  http://127.0.0.1:%BACKEND_PORT%             ║
echo  ║   API文档: http://127.0.0.1:%BACKEND_PORT%/docs       ║
echo  ║                                              ║
echo  ║   关闭方式:                                  ║
echo  ║     - 关闭 ADS-Backend / ADS-Frontend 窗口   ║
echo  ║     - 或运行 stop.bat                        ║
echo  ║                                              ║
echo  ╚══════════════════════════════════════════════╝
echo.

REM 自动打开浏览器
start "" http://127.0.0.1:%FRONTEND_PORT%/

goto :eof

:error_exit
echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║   启动失败，请根据上方提示修复后重试          ║
echo  ╚══════════════════════════════════════════════╝
echo.
pause
exit /b 1
