#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"

if ! command -v temporal >/dev/null 2>&1; then
  echo "Temporal CLI is required. Install it with: brew install temporal" >&2
  exit 1
fi

mkdir -p .data

exec temporal server start-dev \
  --ip "${TEMPORAL_IP:-127.0.0.1}" \
  --port "${TEMPORAL_PORT:-7233}" \
  --ui-port "${TEMPORAL_UI_PORT:-8233}" \
  --db-filename "${TEMPORAL_DB_FILENAME:-.data/temporal.db}" \
  --namespace "${TEMPORAL_NAMESPACE:-default}"

