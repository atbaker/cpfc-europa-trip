#!/usr/bin/env bash
# Reproducible local setup; does not start services or activate a cloud profile.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${repo_root}"
uv sync --locked
npm --prefix frontend ci
uv run --locked python scripts/configure-local.py
echo "Setup complete. Start PostgreSQL and the four development services as described in README.md."
