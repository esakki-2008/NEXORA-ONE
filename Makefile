.PHONY: install-backend test backend frontend-build frontend-test frontend-lint lint typecheck verify

install-backend:
	python -m pip install -e '.[dev]'

backend:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest

frontend-build:
	cd frontend && npm run build

frontend-test:
	cd frontend && npm run test -- --run

frontend-lint:
	cd frontend && npm run lint

lint:
	ruff check backend

typecheck:
	mypy backend/app

verify: lint typecheck test frontend-build frontend-test frontend-lint
