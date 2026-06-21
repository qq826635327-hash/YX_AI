@echo off
chcp 65001 >nul
REM AI Drama Studio - 一键启动开发环境（后端 + 前端）
REM 用法：双击运行或命令行执行 scripts/start-dev.bat

set ROOT=%~dp0..
echo ========================================
echo   AI Drama Studio - 开发环境启动
echo ========================================
echo.

REM 启动后端（新窗口）
echo [1/2] 启动后端 FastAPI (http://127.0.0.1:8000)...
start "AI Drama Studio - Backend" cmd /k "cd /d %ROOT%\backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

REM 启动前端（新窗口）
echo [2/2] 启动前端 Vite (http://localhost:5173)...
start "AI Drama Studio - Frontend" cmd /k "cd /d %ROOT%\frontend && npm run dev"

echo.
echo ========================================
echo   启动完成！
echo   前端: http://localhost:5173
echo   后端 API 文档: http://127.0.0.1:8000/docs
echo ========================================
echo.
echo 两个命令行窗口已打开，关闭对应窗口即可停止服务。
pause
