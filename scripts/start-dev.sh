#!/usr/bin/env bash
# AI Drama Studio - 一键启动开发环境（后端 + 前端）
# 用法：bash scripts/start-dev.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "========================================"
echo "  AI Drama Studio - 开发环境启动"
echo "========================================"
echo ""

# 启动后端
echo "[1/2] 启动后端 FastAPI (http://127.0.0.1:8000)..."
(cd "$ROOT/backend" && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload) &
BACKEND_PID=$!

# 启动前端
echo "[2/2] 启动前端 Vite (http://localhost:5173)..."
(cd "$ROOT/frontend" && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "========================================"
echo "  启动完成！"
echo "  前端: http://localhost:5173"
echo "  后端 API 文档: http://127.0.0.1:8000/docs"
echo "========================================"
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
