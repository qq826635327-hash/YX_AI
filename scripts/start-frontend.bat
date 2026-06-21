@echo off
chcp 65001 >nul
REM 单独启动前端
set ROOT=%~dp0..
cd /d %ROOT%\frontend
echo 启动前端 Vite: http://localhost:5173
npm run dev
