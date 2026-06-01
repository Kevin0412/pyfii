#!/usr/bin/env bash
#
# pyfii-gui 一键启动脚本
#
# 用法:
#   ./start.sh              # 默认: backend :8000 + frontend :5173
#   ./start.sh --port 9000  # 自定义后端端口
#   ./start.sh --no-install # 跳过依赖安装
#   ./start.sh --help
#
set -euo pipefail

# ── 默认配置 ──────────────────────────────────────────────
BACKEND_PORT=8000
FRONTEND_PORT=5173
SKIP_INSTALL=false

# ── 路径推导 ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUI_DIR="$SCRIPT_DIR"
REPO_ROOT="$(cd "$GUI_DIR/../.." && pwd)"
BACKEND_DIR="$GUI_DIR/backend"
FRONTEND_DIR="$GUI_DIR/frontend"

# ── 颜色 ──────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${GREEN}[pyfii-gui]${NC} $*"; }
warn()  { echo -e "${RED}[!]${NC} $*"; }
step()  { echo -e "${CYAN}==>${NC} $*"; }

# ── 参数解析 ──────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)       BACKEND_PORT="$2"; shift 2 ;;
    --no-install) SKIP_INSTALL=true; shift ;;
    -h|--help)
      echo "用法: $0 [选项]"
      echo ""
      echo "选项:"
      echo "  --port PORT      后端端口 (默认 8000)"
      echo "  --no-install     跳过依赖安装"
      echo "  -h, --help       显示帮助"
      exit 0
      ;;
    *) warn "未知参数: $1"; exit 1 ;;
  esac
done

# ── 环境检查 ──────────────────────────────────────────────
check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    warn "未找到 $1，请先安装。"
    exit 1
  fi
}

step "检查运行环境..."
check_cmd python3
check_cmd node
check_cmd npm

# ── 依赖安装 ──────────────────────────────────────────────
if ! $SKIP_INSTALL; then
  step "安装 pyfii core (editable)..."
  (cd "$REPO_ROOT" && pip install -e . 2>&1 | tail -2)

  step "安装 backend 依赖..."
  (cd "$BACKEND_DIR" && pip install -e . 2>&1 | tail -2)

  step "安装 frontend 依赖..."
  (cd "$FRONTEND_DIR" && npm install --silent)
fi

# ── 清理函数 ──────────────────────────────────────────────
cleanup() {
  info "正在停止服务..."
  [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
  info "已停止。"
}
trap cleanup EXIT INT TERM

# ── 启动服务 ──────────────────────────────────────────────

step "启动后端 (FastAPI :$BACKEND_PORT)..."
PYTHONPATH="$BACKEND_DIR/src:$REPO_ROOT/src" \
  python3 -m uvicorn pyfii_gui_api.main:app \
  --host 0.0.0.0 --port "$BACKEND_PORT" \
  --log-level info &
BACKEND_PID=$!

step "启动前端 (Vite :$FRONTEND_PORT)..."
(cd "$FRONTEND_DIR" && \
  VITE_DEV_PORT="$FRONTEND_PORT" \
  VITE_API_PROXY_TARGET="http://localhost:$BACKEND_PORT" \
  npm run dev -- --host 0.0.0.0) &
FRONTEND_PID=$!

echo ""
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "  Backend   → http://localhost:$BACKEND_PORT"
info "  Frontend  → http://localhost:$FRONTEND_PORT"
info "  API docs  → http://localhost:$BACKEND_PORT/docs"
info "  Ctrl+C    停止所有服务"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

wait
