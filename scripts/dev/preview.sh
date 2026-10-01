#!/usr/bin/env bash
# Isolated sample-only mode for machines without a running Docker daemon.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"
mkdir -p .data
export DATABASE_URL="sqlite+aiosqlite:///.data/browser-preview.db"
export PLANNER_MODE=recorded
export EMAIL_MODE=preview
case "${1:-}" in
  migrate) exec uv run --locked cpfc-db upgrade ;;
  api) exec uv run --locked cpfc-api ;;
  worker) exec uv run --locked cpfc-worker ;;
  *) echo "Usage: scripts/dev/preview.sh migrate|api|worker" >&2; exit 2 ;;
esac
