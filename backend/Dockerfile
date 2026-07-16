# --- builder ---------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml ./
COPY src ./src
COPY evaluation ./evaluation
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# --- runtime ---------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src:/app

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY src ./src
COPY evaluation ./evaluation
COPY scripts ./scripts
COPY examples ./examples

RUN adduser --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "triage.api:app", "--host", "0.0.0.0", "--port", "8000"]
