# syntax=docker/dockerfile:1

FROM python:3.12-slim

# Install system dependencies for Playwright
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
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
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency manifest first to leverage Docker layer caching.
# This layer is only invalidated when pyproject.toml changes.
COPY pyproject.toml README.md ./

# Install Python dependencies (cached via BuildKit cache mount).
# Dependencies are resolved from pyproject.toml directly into a temp
# requirements file so this layer is independent of source code changes.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir setuptools wheel && \
    python -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); open('/tmp/requirements.txt','w').write('\n'.join(d['project']['dependencies']))" && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Copy source code and install the package.
# This layer is only invalidated when src/ changes (fast because deps are cached).
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir .

# Install Playwright browsers (cached via BuildKit cache mount for downloads)
RUN --mount=type=cache,target=/root/.cache/ms-playwright \
    playwright install chromium

# Copy application config and scripts (changes here won't invalidate the pip layers above)
COPY config/ ./config/
COPY scripts/ ./scripts/

# Create data directories
RUN mkdir -p data logs extract

EXPOSE 8000

CMD ["uvicorn", "gt_linkedin_scraper.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
