# KNOX backend image: slim Python, non-root, pinned runtime deps only.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install runtime dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application and migrations.
COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

# Run as a non-root user and make /app writable for runtime data dirs.
RUN useradd --create-home --uid 10001 knox \
    && chown -R knox:knox /app
USER knox

EXPOSE 8000

# Apply migrations, then serve (exec keeps uvicorn as PID 1 for clean signals).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
