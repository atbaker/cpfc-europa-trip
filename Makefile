.PHONY: setup postgres temporal api worker frontend evals check

setup:
	uv sync --all-groups
	cd frontend && npm ci

postgres:
	./scripts/dev/postgres-up.sh

temporal:
	./scripts/dev/temporal-server.sh

api:
	./scripts/dev/api.sh

worker:
	./scripts/dev/worker.sh

frontend:
	./scripts/dev/frontend.sh

evals:
	uv run python -m evals.mock_planner

check:
	./scripts/check.sh
