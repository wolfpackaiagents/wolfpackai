FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

COPY framework /app/framework
WORKDIR /app/framework
RUN pip install --no-cache-dir -e ".[qdrant,pgvector,knowledge]" || pip install --no-cache-dir -e .

EXPOSE 8000 5173
CMD ["python", "-m", "wolfpack"]