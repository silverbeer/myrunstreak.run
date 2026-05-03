FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install dependencies first for better layer caching
COPY backend/pyproject.toml ./backend/
RUN cd backend && uv export --no-emit-project --no-dev -o /tmp/requirements.txt && \
    uv pip install --system --no-cache -r /tmp/requirements.txt

# Copy source — backend/ is the new world; src/shared/ is lifted as-is for
# now and will move under backend/shared/ once the Lambdas are decommissioned.
COPY backend/ /app/backend/
COPY src/shared /app/src/shared
RUN touch /app/src/__init__.py

# Non-root user
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# uvicorn entry. Replicas can scale horizontally; one worker per pod is fine.
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
