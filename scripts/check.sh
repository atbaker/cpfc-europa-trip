#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run mypy src evals
uv run pytest

terraform fmt -check -recursive infra
terraform -chdir=infra/bootstrap init -backend=false -input=false -lockfile=readonly >/dev/null
terraform -chdir=infra/bootstrap validate
terraform -chdir=infra/envs/prod init -backend=false -input=false -lockfile=readonly >/dev/null
terraform -chdir=infra/envs/prod validate

cd frontend
npm run typecheck
npm run lint
npm run test
npm run build

test -f out/index.html
test -f out/plan/index.html
test -n "$(find out/_next/static -type f -print -quit)"
