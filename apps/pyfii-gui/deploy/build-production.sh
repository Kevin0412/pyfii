#!/usr/bin/env bash
# Reproducibly build the same-origin production frontend from package-lock.json.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/../frontend" && pwd)"

if [[ $# -ne 0 ]]; then
  echo "Usage: $0" >&2
  exit 2
fi

command -v node >/dev/null 2>&1 || { echo "node is required" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required" >&2; exit 1; }

node - <<'NODE'
const [major, minor] = process.versions.node.split('.').map(Number)
const supported =
  (major === 20 && minor >= 19) ||
  (major === 22 && minor >= 12) ||
  major > 22

if (!supported) {
  console.error(
    `Node ${process.versions.node} is unsupported; use ^20.19.0 or >=22.12.0.`,
  )
  process.exit(1)
}
NODE

npm --prefix "$FRONTEND_DIR" ci
VITE_API_BASE_URL= npm --prefix "$FRONTEND_DIR" run build
"$SCRIPT_DIR/check-production.sh" --dist "$FRONTEND_DIR/dist" --skip-health
