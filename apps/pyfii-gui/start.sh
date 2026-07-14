#!/usr/bin/env bash
#
# pyfii-gui 一键启动脚本
#
# 用法:
#   ./start.sh              # 默认: backend :8000 + frontend :5173
#   ./start.sh --port 9000  # 自定义后端端口
#   ./start.sh --frontend-port 5174
#   ./start.sh --no-install # 跳过依赖安装
#   PYFII_GUI_LOG_DIR=/path/to/logs ./start.sh
#   ./start.sh --help
#
set -euo pipefail

# ── 默认配置 ──────────────────────────────────────────────
BACKEND_PORT=8000
FRONTEND_PORT=5173
SKIP_INSTALL=false
PYTHON_BIN="${PYTHON:-python3}"

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
    --port)
      [[ $# -ge 2 ]] || { warn "--port 需要端口号"; exit 1; }
      BACKEND_PORT="$2"; shift 2
      ;;
    --frontend-port)
      [[ $# -ge 2 ]] || { warn "--frontend-port 需要端口号"; exit 1; }
      FRONTEND_PORT="$2"; shift 2
      ;;
    --no-install) SKIP_INSTALL=true; shift ;;
    -h|--help)
      echo "用法: $0 [选项]"
      echo ""
      echo "选项:"
      echo "  --port PORT      后端端口 (默认 8000)"
      echo "  --frontend-port PORT  前端端口 (默认 5173)"
      echo "  --no-install     跳过依赖安装"
      echo "  -h, --help       显示帮助"
      exit 0
      ;;
    *) warn "未知参数: $1"; exit 1 ;;
  esac
done

valid_port() {
  [[ "$1" =~ ^[0-9]+$ ]] && (( 1 <= 10#$1 && 10#$1 <= 65535 ))
}

valid_port "$BACKEND_PORT" || { warn "无效的后端端口: $BACKEND_PORT"; exit 1; }
valid_port "$FRONTEND_PORT" || { warn "无效的前端端口: $FRONTEND_PORT"; exit 1; }

# ── 环境检查 ──────────────────────────────────────────────
check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    warn "未找到 $1，请先安装。"
    exit 1
  fi
}

step "检查运行环境..."
check_cmd "$PYTHON_BIN"
check_cmd node
check_cmd npm

# ── 依赖安装 ──────────────────────────────────────────────
if ! $SKIP_INSTALL; then
  step "安装 pyfii core (editable)..."
  "$PYTHON_BIN" -m pip install -e "$REPO_ROOT"

  step "安装 backend 依赖..."
  "$PYTHON_BIN" -m pip install -e "$BACKEND_DIR"

  step "安装 frontend 依赖..."
  npm --prefix "$FRONTEND_DIR" install
fi

if [[ ! -x "$FRONTEND_DIR/node_modules/.bin/vite" ]]; then
  warn "前端依赖未安装，请去掉 --no-install 后重试。"
  exit 1
fi

# ── 运行日志 ──────────────────────────────────────────────
# 每次启动使用独立目录，避免覆盖上一次运行。
LOG_ROOT="${PYFII_GUI_LOG_DIR:-$GUI_DIR/logs}"
RUN_LOG_DIR="$LOG_ROOT/$(date '+%Y%m%d-%H%M%S')-$$"
BACKEND_LOG="$RUN_LOG_DIR/backend.log"
FRONTEND_LOG="$RUN_LOG_DIR/frontend.log"
mkdir -p "$RUN_LOG_DIR"

# 终端保持服务的原始输出；写入文件时统一补上本地时间和时区。
timestamp_log_stream() {
  local log_file="$1"
  local line
  exec 3>>"$log_file"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    printf '%s\n' "$line"
    printf '[%(%Y-%m-%d %H:%M:%S %z)T] %s\n' -1 "$line" >&3
  done
  exec 3>&-
}

# ── 清理函数 ──────────────────────────────────────────────
cleanup() {
  local status=$?
  trap - EXIT INT TERM
  info "正在停止服务..."
  [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null || true
  [ -n "${FRONTEND_PID:-}" ] && kill "$FRONTEND_PID" 2>/dev/null || true
  wait "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
  info "已停止。"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# ── 启动服务 ──────────────────────────────────────────────

step "启动后端 (FastAPI :$BACKEND_PORT)..."
(
  cd "$REPO_ROOT"
  export PYTHONPATH="$BACKEND_DIR/src:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
  exec "$PYTHON_BIN" -m uvicorn pyfii_gui_api.main:app \
    --host 0.0.0.0 --port "$BACKEND_PORT" --log-level info \
    > >(timestamp_log_stream "$BACKEND_LOG") 2>&1
) &
BACKEND_PID=$!

step "启动前端 (Vite :$FRONTEND_PORT)..."
(
  cd "$FRONTEND_DIR"
  export VITE_DEV_HOST=0.0.0.0
  export VITE_DEV_PORT="$FRONTEND_PORT"
  export VITE_API_PROXY_TARGET="http://localhost:$BACKEND_PORT"
  exec ./node_modules/.bin/vite > >(timestamp_log_stream "$FRONTEND_LOG") 2>&1
) &
FRONTEND_PID=$!

echo ""
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
info "  Backend   → http://localhost:$BACKEND_PORT"
info "  Frontend  → http://localhost:$FRONTEND_PORT"
info "  API docs  → http://localhost:$BACKEND_PORT/docs"
info "  Logs      → $RUN_LOG_DIR"
info "  Ctrl+C    停止所有服务"
info "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

set +e
wait -n "$BACKEND_PID" "$FRONTEND_PID"
STATUS=$?
set -e
warn "有服务已退出，正在停止另一端。"
exit "$STATUS"
