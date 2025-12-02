FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY contracts ./contracts
COPY backend-service ./backend-service
RUN pip install --no-cache-dir ./contracts ./backend-service

EXPOSE 8000
CMD ["uvicorn", "backend_service.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
