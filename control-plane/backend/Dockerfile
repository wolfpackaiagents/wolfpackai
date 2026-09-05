FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/control-plane/backend/.venv/bin:$PATH"

COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /uvx /bin/

WORKDIR /app

COPY framework /app/framework
COPY control-plane/backend /app/control-plane/backend

RUN uv sync --directory /app/control-plane/backend --frozen --no-dev \
    && useradd --create-home --uid 10001 wolfpack

WORKDIR /app/control-plane/backend
USER wolfpack

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health')"

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
