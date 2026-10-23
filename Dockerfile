# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# ---------------------------------------------------------
# System dependencies required by Chromium
# ---------------------------------------------------------
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        libnss3 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libcups2 \
        libdbus-1-3 \
        libxkbcommon0 \
        libatspi2.0-0 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libgbm1 \
        libpango-1.0-0 \
        libcairo2 \
        libasound2 \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------
COPY pyproject.toml README.md ./

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); open('/tmp/requirements.txt','w').write('\n'.join(d['project']['dependencies']))" && \
    pip install -r /tmp/requirements.txt

# ---------------------------------------------------------
# Application
# ---------------------------------------------------------
COPY src/ ./src/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install .

COPY config/ ./config/
COPY scripts/ ./scripts/
COPY alembic.ini ./
COPY alembic/ ./alembic/

# ---------------------------------------------------------
# Install Playwright Chromium
# ---------------------------------------------------------
RUN --mount=type=cache,target=/root/.cache/ms-playwright \
    playwright install chromium

# ---------------------------------------------------------
# Verify Chromium was actually installed
# ---------------------------------------------------------
RUN playwright install --list && \
    python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); print(p.chromium.executable_path); p.stop()"

# ---------------------------------------------------------
# Runtime directories
# ---------------------------------------------------------
RUN mkdir -p runtime/data runtime/logs runtime/extract runtime/debug runtime/resumes

EXPOSE 8000

CMD ["uvicorn", "gt_linkedin_scraper.api.main:app", "--host", "0.0.0.0", "--port", "8000"]