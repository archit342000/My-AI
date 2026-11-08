#!/usr/bin/env bash
# Runs all project checks locally (there is no hosted CI).
# Usage: scripts/check.sh [--python-only | --frontend-only]
set -u
cd "$(dirname "$0")/.."

PY="venv/bin/python"
ROOT="$(pwd)"
[ -x "$PY" ] && PY="$ROOT/$PY" || PY="python3"
export EMBEDDING_URL="${EMBEDDING_URL:-http://mock}" AI_URL="${AI_URL:-http://mock}" AI_API_KEY="${AI_API_KEY:-dummy}" PYTHONPATH=.

run_python=1; run_frontend=1
case "${1:-}" in
  --python-only) run_frontend=0 ;;
  --frontend-only) run_python=0 ;;
  "") ;;
  *) echo "usage: $0 [--python-only | --frontend-only]"; exit 2 ;;
esac

failed=()
step() { # step <name> <dir> <command...>
  local name="$1" dir="$2"; shift 2
  echo; echo "=== $name"
  if (cd "$dir" && "$@"); then echo "--- PASS: $name"; else echo "--- FAIL: $name"; failed+=("$name"); fi
}

if [ "$run_python" = 1 ]; then
  step "ruff"             .               "$PY" -m ruff check .
  step "docs guardrails"  .               "$PY" -m pytest tests -q -p no:cacheprovider
  step "backend"          .               "$PY" -m pytest backend -q -p no:cacheprovider
  step "inference_proxy"  .               "$PY" -m pytest inference_proxy -q -p no:cacheprovider
  step "tavily_mcp"       .               "$PY" -m pytest tavily_mcp -q -p no:cacheprovider
  step "code_runner_mcp"  code_runner_mcp env PYTHONPATH=. "$PY" -m pytest -q -p no:cacheprovider
fi

if [ "$run_frontend" = 1 ]; then
  step "frontend typecheck" frontend npm run typecheck --silent
  step "frontend lint"      frontend npm run lint --silent
  step "frontend test"      frontend npm run test --silent
  step "frontend build"     frontend npm run build --silent
fi

echo
if [ ${#failed[@]} -eq 0 ]; then echo "ALL CHECKS PASSED"; exit 0; fi
echo "FAILED: ${failed[*]}"; exit 1
