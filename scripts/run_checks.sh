#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python}"
if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN=".venv/bin/python"
fi
RUFF_BIN="${RUFF_BIN:-ruff}"
if [[ -x ".venv/bin/ruff" ]]; then
  RUFF_BIN=".venv/bin/ruff"
fi
MYPY_BIN="${MYPY_BIN:-mypy}"
if [[ -x ".venv/bin/mypy" ]]; then
  MYPY_BIN=".venv/bin/mypy"
fi

"$PYTHON_BIN" -m pytest
"$RUFF_BIN" check backend
"$MYPY_BIN" backend/app
"$PYTHON_BIN" -m pip_audit
"$PYTHON_BIN" -m bandit -q -r backend/app
(
  cd frontend
  npm run typecheck
  npm run lint
  npm run test -- --run
  npm run build
  npm audit --audit-level=high
)

./scripts/check_secrets.sh
