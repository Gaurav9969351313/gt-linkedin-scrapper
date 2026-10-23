.PHONY: help install docker docker-infra docker-down migrate seed super-admin \
        api worker prefect-server dev streamlit web-api web web-install web-build \
        add-candidate test clean

INFRA = postgres prefect-server pgadmin

help:
	@echo "Docker"
	@echo "  make docker          Build and start everything (scraper, Streamlit :8501, web :8502)"
	@echo "  make docker-infra    Start only Postgres, Prefect and pgAdmin (for local development)"
	@echo "  make docker-down     Stop all containers"
	@echo "Database"
	@echo "  make migrate         Apply Alembic migrations"
	@echo "  make seed            Migrate and seed jobs from config/jobs.yaml"
	@echo "  make super-admin EMAIL=you@example.com NAME=\"Your Name\""
	@echo "Local development (run 'make docker-infra' first)"
	@echo "  make api / worker    Scraper API :8000 / Prefect worker"
	@echo "  make streamlit       Streamlit UI :8501"
	@echo "  make web-api / web   Web API :8502 / Angular dev server :4300"
	@echo "  make test            Run the test suite"

install:
	pip install -e ".[dev,streamlit]"
	playwright install chromium

# ---- Docker ----

docker:
	docker compose up -d --build

docker-infra:
	docker compose up -d $(INFRA)

docker-down:
	docker compose down

# ---- Database ----

migrate:
	python scripts/migrate.py

seed: migrate
	python scripts/seed_jobs.py

# usage: make super-admin EMAIL=you@example.com NAME="Your Name"   (prompts for a password)
super-admin:
	python -m gt_linkedin_scraper.web.cli --email "$(EMAIL)" --name "$(NAME)"

# usage: make add-candidate ARGS="--resume path/to/cv.pdf"
add-candidate:
	python scripts/insert_candidate_from_email.py $(ARGS)

# ---- Local development ----

prefect-server:
	prefect server start --host 0.0.0.0 --port 4200

worker:
	python scripts/start_worker.py

api:
	uvicorn gt_linkedin_scraper.api.main:app --host 0.0.0.0 --port 8000 --reload

dev:
	python scripts/dev_runner.py

streamlit:
	streamlit run apps/streamlit/app.py --server.port=8501 --server.headless=true --secrets.files=apps/streamlit/.streamlit/secrets.toml

web-install:
	cd apps/web && npm install

# Web API on :8502; also serves the built Angular app if apps/web/dist exists (make web-build)
web-api:
	uvicorn gt_linkedin_scraper.web.app:app --host 0.0.0.0 --port 8502 --reload --reload-dir src

# Angular dev server on :4300, proxies /api to :8502
web:
	cd apps/web && npm start

web-build:
	cd apps/web && npx ng build

test:
	pytest

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
	find . -name __pycache__ -type d -prune -not -path "./.venv/*" -not -path "./apps/web/node_modules/*" -exec rm -rf {} +
