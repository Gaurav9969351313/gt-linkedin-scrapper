.PHONY: install prefect-server worker api dev dev-docker seed docker clean

install:
	pip install -e ".[dev]"
	playwright install chromium

prefect-server:
	prefect server start --host 0.0.0.0 --port 4200

worker:
	prefect worker start --pool default

api:
	uvicorn gt_linkedin_scraper.api.main:app --host 0.0.0.0 --port 8000 --reload

dev:
	python scripts/dev_runner.py

dev-docker:
	docker compose -f docker-compose.dev.yml up -d
	@echo "Postgres and Prefect server started in Docker."
	@echo "Now run: make api (in one terminal) && make worker (in another)"

seed:
	alembic upgrade head
	python scripts/seed_jobs.py

docker:
	docker compose up --build

clean:
	rm -rf __pycache__ *.pyc .pytest_cache .mypy_cache .ruff_cache
