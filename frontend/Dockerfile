# syntax=docker/dockerfile:1

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/

RUN pip install --no-cache-dir -e ".[frontend]"

COPY frontend/ ./frontend/

EXPOSE 8501

CMD ["streamlit", "run", "frontend/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
