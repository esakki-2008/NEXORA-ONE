#!/usr/bin/env bash
set -euo pipefail

# The operations/intelligence layer is data-only. Keep this scan intentionally
# narrow and exclude this scanner's own pattern literals.
if grep -RInE \
  --exclude-dir=.venv \
  --exclude-dir=node_modules \
  --exclude-dir=dist \
  --exclude-dir=.git \
  --exclude='*.pyc' \
  --exclude='check_execution.sh' \
  '(subprocess|os\.system|shell[[:space:]]*=|eval\(|exec\(|pickle|yaml\.unsafe_load)' \
  backend frontend scripts; then
  echo "Forbidden execution pattern found" >&2
  exit 1
fi

if grep -RIn \
  --exclude-dir=node_modules \
  --exclude-dir=dist \
  -E '(NEBIUS_API_KEY|sk-[A-Za-z0-9]{20,}|Bearer[[:space:]]+[A-Za-z0-9._-]{20,})' \
  frontend; then
  echo "Frontend credential pattern found" >&2
  exit 1
fi

echo "Forbidden execution scan passed."
echo "Frontend credential scan passed."
