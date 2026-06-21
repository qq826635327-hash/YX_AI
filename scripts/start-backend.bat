@echo off
chcp 65001 >nul
REM 单独启动后端
set ROOT=%~dp0..
cd /d %ROOT%\backend
echo 启动后端 FastAPI: http://127.0.0.1:8000
echo API 文档: http://127.0.0.1:8000/docs
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
