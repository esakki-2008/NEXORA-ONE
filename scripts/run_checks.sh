#!/usr/bin/env bash
set -euo pipefail

python -m pytest
ruff check backend
mypy backend/app
(
  cd frontend
  npm run typecheck
  npm run test -- --run
  npm run build
)
