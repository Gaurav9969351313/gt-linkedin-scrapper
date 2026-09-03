FROM python:3.12-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
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

# Copy source code first for editable install
COPY pyproject.toml .
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Install Playwright browsers
RUN playwright install chromium

# Create data directories
RUN mkdir -p data logs extract

EXPOSE 8000

CMD ["uvicorn", "gt_linkedin_scraper.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
