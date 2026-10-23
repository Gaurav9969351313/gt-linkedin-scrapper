# syntax=docker/dockerfile:1
# Build from the repo root: docker build -f apps/web/Dockerfile .

# ---- build the Angular app ----
FROM node:20-alpine AS build
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY apps/web/ ./
RUN npx ng build --configuration production

# ---- web API + static files ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEB_STATIC_DIR=/app/static

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=120 --retries 5 .

COPY --from=build /web/dist/web/browser ./static

EXPOSE 8502

CMD ["uvicorn", "gt_linkedin_scraper.web.app:app", "--host", "0.0.0.0", "--port", "8502"]
