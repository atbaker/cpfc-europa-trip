#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"

docker compose up --detach --wait postgres
uv run cpfc-db upgrade
echo "PostgreSQL is ready and migrated at localhost:${POSTGRES_PORT:-5432}."

