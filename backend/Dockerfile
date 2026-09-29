# KNOX backend image: slim Python, non-root, pinned runtime deps only.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install git (required for repository acquisition and git history analysis)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Install runtime dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application and migrations.
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

# Run as a non-root user and make /app writable for runtime data dirs.
RUN useradd --create-home --uid 10001 knox \
    && mkdir -p /app/data /app/knowledge_packages /app/exports /app/analysis_workspace \
    && chown -R knox:knox /app
USER knox

VOLUME ["/app/data", "/app/knowledge_packages", "/app/exports", "/app/analysis_workspace"]

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/readyz')" || exit 1

# Apply migrations, then serve (exec keeps uvicorn as PID 1 for clean signals).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

