#!/usr/bin/env bash
set -euo pipefail

# This check looks for values, not variable names. The example file is allowed
# to contain empty configuration keys but must not contain credential material.
if git grep -n -I -E '(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|password[[:space:]]*=[[:space:]]*[^[:space:]]+)' -- . ':(exclude).env.example' ':(exclude)scripts/check_secrets.sh'; then
  echo "Potential credential material found. Review the matches before committing." >&2
  exit 1
fi

echo "No credential patterns found in tracked files."
