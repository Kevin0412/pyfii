#!/usr/bin/env bash
# Validate a production frontend build and, unless disabled, the local API.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUI_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="${PYFII_GUI_DIST_ROOT:-$GUI_DIR/frontend/dist}"
HEALTH_URL="${PYFII_GUI_HEALTH_URL:-http://127.0.0.1:8000/api/health}"
SITE_URL="${PYFII_GUI_SITE_URL:-}"
CHECK_HEALTH=true

usage() {
  cat <<'EOF'
Usage: check-production.sh [--dist DIR] [--health-url URL] [--site-url URL]
                           [--skip-health]

Checks that the Vite production build exists and contains no dev-server entry.
When Caddy is installed, it also validates deploy/Caddyfile.example. By default
the running backend health endpoint is checked with curl. --site-url additionally
checks that the deployed public page is not a Vite development entry.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dist)
      [[ $# -ge 2 ]] || { echo "--dist requires a directory" >&2; exit 2; }
      DIST_DIR="$2"
      shift 2
      ;;
    --health-url)
      [[ $# -ge 2 ]] || { echo "--health-url requires a URL" >&2; exit 2; }
      HEALTH_URL="$2"
      shift 2
      ;;
    --site-url)
      [[ $# -ge 2 ]] || { echo "--site-url requires a URL" >&2; exit 2; }
      SITE_URL="$2"
      shift 2
      ;;
    --skip-health)
      CHECK_HEALTH=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

fail() {
  echo "[FAIL] $*" >&2
  exit 1
}

pass() {
  echo "[ OK ] $*"
}

warn() {
  echo "[WARN] $*" >&2
}

check_production_entry() {
  local index_file="$1"
  local label="$2"

  if grep -Fq '/@vite/client' "$index_file"; then
    fail "$label still loads the Vite development client"
  fi
  if grep -Fq 'src="/src/' "$index_file" || grep -Fq "src='/src/" "$index_file"; then
    fail "$label still loads frontend source files"
  fi
}

INDEX_FILE="$DIST_DIR/index.html"
[[ -r "$INDEX_FILE" ]] || fail "missing readable production entry: $INDEX_FILE"
[[ -d "$DIST_DIR/assets" ]] || fail "missing Vite assets directory: $DIST_DIR/assets"
[[ -n "$(find "$DIST_DIR/assets" -type f -print -quit)" ]] || fail "assets directory is empty"
[[ -z "$(find "$DIST_DIR" -type l -print -quit)" ]] || fail "dist contains symbolic links"

check_production_entry "$INDEX_FILE" "index.html"
pass "production frontend entry and assets"

if [[ -n "$SITE_URL" ]]; then
  command -v curl >/dev/null 2>&1 || fail "curl is required for the public site check"
  PUBLIC_INDEX="$(mktemp)"
  trap 'rm -f "$PUBLIC_INDEX"' EXIT
  curl --fail --silent --show-error --max-time 15 "$SITE_URL" > "$PUBLIC_INDEX"
  check_production_entry "$PUBLIC_INDEX" "$SITE_URL"
  pass "public site uses a production entry: $SITE_URL"
fi

if command -v caddy >/dev/null 2>&1; then
  PYFII_GUI_DOMAIN=localhost \
  PYFII_GUI_DIST_ROOT="$DIST_DIR" \
  PYFII_GUI_BACKEND=127.0.0.1:8000 \
    caddy validate --config "$SCRIPT_DIR/Caddyfile.example"
  pass "Caddyfile syntax"
else
  warn "caddy is not installed; skipped Caddyfile validation"
fi

if $CHECK_HEALTH; then
  command -v curl >/dev/null 2>&1 || fail "curl is required for the health check"
  curl --fail --silent --show-error --max-time 10 "$HEALTH_URL" >/dev/null
  pass "backend health endpoint: $HEALTH_URL"
else
  warn "backend health check skipped"
fi
