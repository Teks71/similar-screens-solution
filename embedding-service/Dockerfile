# syntax=docker/dockerfile:1.7
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt --mount=type=cache,target=/var/lib/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

# Preinstall torch (largest dependency) in its own layer to reuse cache across code changes
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --extra-index-url https://download.pytorch.org/whl/cu118 torch==2.3.1

COPY contracts ./contracts
COPY embedding-service ./embedding-service

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ./contracts ./embedding-service

EXPOSE 8001
CMD ["uvicorn", "embedding_service.app:app", "--host", "0.0.0.0", "--port", "8001"]
