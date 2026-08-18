# syntax=docker/dockerfile:1

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

# Install runtime dependencies before copying application code
# to improve Docker layer caching.
COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

# Copy only the files required by the application and migrations.
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
COPY scripts ./scripts

# Run the container as a non-root user.
RUN addgroup --system britmart \
    && adduser --system --ingroup britmart britmart \
    && chown -R britmart:britmart /app

USER britmart

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)" || exit 1

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]