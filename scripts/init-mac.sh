#!/usr/bin/env bash
# AI Drama Studio - Mac 环境初始化脚本
# 功能：将 node_modules 和 .venv 移出坚果云同步目录，用 symlink 指回来
# 用法：bash scripts/init-mac.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STORAGE="$HOME/Documents/ai-drama-studio-env"

echo "========================================"
echo "  AI Drama Studio - Mac 环境初始化"
echo "========================================"
echo ""

# ── 前端 ──
echo "[1/2] 初始化前端环境..."

FRONTEND_DIR="$ROOT/frontend"
FRONTEND_STORAGE="$STORAGE/frontend"

# 如果 node_modules 是真实目录（被坚果云同步覆盖了），移出去
if [ -d "$FRONTEND_DIR/node_modules" ] && [ ! -L "$FRONTEND_DIR/node_modules" ]; then
    echo "  发现坚果云同步的 node_modules（非 symlink），正在移出..."
    mkdir -p "$FRONTEND_STORAGE"
    rm -rf "$FRONTEND_STORAGE/node_modules"
    mv "$FRONTEND_DIR/node_modules" "$FRONTEND_STORAGE/node_modules"
fi

# 如果目标目录不存在，先 npm install 到外部目录
if [ ! -d "$FRONTEND_STORAGE/node_modules" ]; then
    echo "  在外部目录执行 npm install..."
    mkdir -p "$FRONTEND_STORAGE"
    (cd "$FRONTEND_DIR" && npm install --prefix "$FRONTEND_STORAGE" --cache "$FRONTEND_STORAGE/.npm-cache")
    # 把安装好的 node_modules 移到正确位置
    if [ -d "$FRONTEND_DIR/node_modules" ] && [ ! -L "$FRONTEND_DIR/node_modules" ]; then
        mv "$FRONTEND_DIR/node_modules" "$FRONTEND_STORAGE/node_modules"
    fi
fi

# 创建 symlink（如果不存在）
if [ ! -L "$FRONTEND_DIR/node_modules" ]; then
    ln -s "$FRONTEND_STORAGE/node_modules" "$FRONTEND_DIR/node_modules"
    echo "  symlink 已创建: node_modules -> $FRONTEND_STORAGE/node_modules"
else
    echo "  symlink 已存在，跳过"
fi

# ── 后端 ──
echo "[2/2] 初始化后端环境..."

BACKEND_DIR="$ROOT/backend"
BACKEND_STORAGE="$STORAGE/backend"

# 如果 .venv 是真实目录（被坚果云同步覆盖了），移出去
if [ -d "$BACKEND_DIR/.venv" ] && [ ! -L "$BACKEND_DIR/.venv" ]; then
    echo "  发现坚果云同步的 .venv（非 symlink），正在移出..."
    mkdir -p "$BACKEND_STORAGE"
    rm -rf "$BACKEND_STORAGE/.venv"
    mv "$BACKEND_DIR/.venv" "$BACKEND_STORAGE/.venv"
fi

# 如果目标目录不存在，先创建 venv
if [ ! -d "$BACKEND_STORAGE/.venv" ]; then
    echo "  创建 Python 虚拟环境..."
    mkdir -p "$BACKEND_STORAGE"
    # 优先使用 Python 3.11+
    PYTHON=""
    for cmd in python3.11 python3.12 python3.13 python3; do
        if command -v "$cmd" &>/dev/null; then
            ver=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            major=$(echo "$ver" | cut -d. -f1)
            minor=$(echo "$ver" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
                PYTHON="$cmd"
                break
            fi
        fi
    done
    if [ -z "$PYTHON" ]; then
        echo "  错误: 未找到 Python 3.11+，请先安装"
        exit 1
    fi
    echo "  使用 Python: $PYTHON ($($PYTHON --version))"
    "$PYTHON" -m venv "$BACKEND_STORAGE/.venv"
    (source "$BACKEND_STORAGE/.venv/bin/activate" && pip install -e "$BACKEND_DIR[dev]")
fi

# 创建 symlink（如果不存在）
if [ ! -L "$BACKEND_DIR/.venv" ]; then
    ln -s "$BACKEND_STORAGE/.venv" "$BACKEND_DIR/.venv"
    echo "  symlink 已创建: .venv -> $BACKEND_STORAGE/.venv"
else
    echo "  symlink 已存在，跳过"
fi

echo ""
echo "========================================"
echo "  初始化完成！"
echo "  node_modules 和 .venv 已存放在:"
echo "  $STORAGE"
echo ""
echo "  启动开发环境: bash scripts/start-dev.sh"
echo "========================================"
