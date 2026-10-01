#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"
uv lock --check
uv run --locked ruff format --check src tests migrations scripts
uv run --locked ruff check src tests migrations scripts
uv run --locked mypy src
uv run --locked pytest
uv run --locked python scripts/export-openapi.py
cp frontend/lib/api-schema.ts .data/api-schema-before.ts
npm --prefix frontend run generate:api
cmp frontend/lib/api-schema.ts .data/api-schema-before.ts
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run test
NEXT_PUBLIC_API_ORIGIN= npm --prefix frontend run build
test -f frontend/out/index.html
test -f frontend/out/plan/index.html
test -f frontend/out/privacy/index.html
# Infrastructure/release checks join this gate as that milestone is implemented.
