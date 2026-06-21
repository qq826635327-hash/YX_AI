#!/usr/bin/env bash
# ============================================================
#  AI Drama Studio - 一键启动脚本 (macOS / Linux)
#  位置：项目根目录 start.sh
#  用法：bash start.sh 或 chmod +x start.sh && ./start.sh
# ============================================================

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║     AI Drama Studio - 一键启动              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# ============================================================
#  1. 环境检查
# ============================================================
echo "[1/5] 检查运行环境..."

if ! command -v python3 &> /dev/null; then
    echo -e "  ${RED}[X] 未找到 Python3，请先安装 Python 3.11+${NC}"
    exit 1
fi
echo -e "  ${GREEN}[ok] Python $(python3 --version 2>&1)${NC}"

if ! command -v node &> /dev/null; then
    echo -e "  ${RED}[X] 未找到 Node.js，请先安装 Node.js 18+${NC}"
    exit 1
fi
echo -e "  ${GREEN}[ok] Node.js $(node --version)${NC}"

# 检查虚拟环境
if [ ! -f "$ROOT/backend/.venv/bin/python" ] && [ ! -f "$ROOT/backend/.venv/Scripts/python.exe" ]; then
    echo -e "  ${RED}[X] 后端虚拟环境不存在，请先运行: bash scripts/init-backend.sh${NC}"
    exit 1
fi
echo -e "  ${GREEN}[ok] 后端虚拟环境已就绪${NC}"

# 检查前端依赖
if [ ! -d "$ROOT/frontend/node_modules" ]; then
    echo -e "  ${YELLOW}[!] 前端依赖未安装，正在执行 npm install...${NC}"
    (cd "$ROOT/frontend" && npm install --silent)
fi
echo -e "  ${GREEN}[ok] 前端依赖已就绪${NC}"

# ============================================================
#  2. 端口检查
# ============================================================
echo ""
echo "[2/5] 检查端口占用..."

kill_port() {
    local port=$1
    local pid=$(lsof -ti :$port 2>/dev/null || true)
    if [ -n "$pid" ]; then
        echo -e "  ${YELLOW}[!] 端口 $port 被 PID $pid 占用，正在释放...${NC}"
        kill -9 $pid 2>/dev/null || true
        sleep 1
        echo -e "  ${GREEN}[ok] 端口 $port 已释放${NC}"
    else
        echo -e "  ${GREEN}[ok] 端口 $port 可用${NC}"
    fi
}

kill_port $BACKEND_PORT
kill_port $FRONTEND_PORT

# ============================================================
#  3. 启动后端
# ============================================================
echo ""
echo "[3/5] 启动后端 FastAPI (http://127.0.0.1:$BACKEND_PORT)..."

PYTHON="$ROOT/backend/.venv/bin/python"
[ ! -f "$PYTHON" ] && PYTHON="$ROOT/backend/.venv/Scripts/python.exe"

(cd "$ROOT/backend" && $PYTHON -m uvicorn app.main:app \
    --host 127.0.0.1 --port $BACKEND_PORT) &
BACKEND_PID=$!

# 等待后端就绪
echo "  等待后端启动..."
BACKEND_READY=0
for i in $(seq 1 15); do
    if curl -s http://127.0.0.1:$BACKEND_PORT/api/health > /dev/null 2>&1; then
        BACKEND_READY=1
        echo -e "  ${GREEN}[ok] 后端已就绪 (${i} 秒)${NC}"
        break
    fi
    sleep 1
done

if [ $BACKEND_READY -eq 0 ]; then
    echo -e "  ${YELLOW}[!] 后端启动较慢，前端将继续启动...${NC}"
fi

# ============================================================
#  4. 启动前端
# ============================================================
echo ""
echo "[4/5] 启动前端 Vite (http://127.0.0.1:$FRONTEND_PORT)..."

(cd "$ROOT/frontend" && npx vite --host 127.0.0.1) &
FRONTEND_PID=$!

# 等待前端就绪
echo "  等待前端启动..."
FRONTEND_READY=0
for i in $(seq 1 10); do
    if curl -s -o /dev/null http://127.0.0.1:$FRONTEND_PORT/ 2>/dev/null; then
        FRONTEND_READY=1
        echo -e "  ${GREEN}[ok] 前端已就绪 (${i} 秒)${NC}"
        break
    fi
    sleep 1
done

if [ $FRONTEND_READY -eq 0 ]; then
    echo -e "  ${YELLOW}[!] 前端启动较慢，请稍后手动访问验证${NC}"
fi

# ============================================================
#  5. 就绪提示
# ============================================================
echo ""
echo "[5/5] 启动结果"
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║                                              ║"
echo "  ║   前端:    http://127.0.0.1:$FRONTEND_PORT             ║"
echo "  ║   后端:    http://127.0.0.1:$BACKEND_PORT             ║"
echo "  ║   API文档: http://127.0.0.1:$BACKEND_PORT/docs        ║"
echo "  ║                                              ║"
echo "  ║   按 Ctrl+C 停止所有服务                     ║"
echo "  ║                                              ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""

# 尝试打开浏览器
if command -v open &> /dev/null; then
    open "http://127.0.0.1:$FRONTEND_PORT" 2>/dev/null || true
elif command -v xdg-open &> /dev/null; then
    xdg-open "http://127.0.0.1:$FRONTEND_PORT" 2>/dev/null || true
fi

# Ctrl+C 停止所有服务
cleanup() {
    echo ""
    echo "  正在停止服务..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    echo "  所有服务已停止。"
    exit 0
}

trap cleanup INT TERM
wait
