# syntax=docker/dockerfile:1
# Build from the repo root: docker build -f apps/streamlit/Dockerfile .

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --default-timeout=120 --retries 5 ".[streamlit]"

COPY apps/streamlit/ ./apps/streamlit/

EXPOSE 8501

# Secrets are mounted at runtime (see docker-compose.yml); the image never contains them.
CMD ["streamlit", "run", "apps/streamlit/app.py", "--server.port=8501", "--server.address=0.0.0.0", "--secrets.files=apps/streamlit/.streamlit/secrets.toml"]
