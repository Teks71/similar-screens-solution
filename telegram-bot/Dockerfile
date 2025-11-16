FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

COPY contracts ./contracts
COPY telegram-bot ./telegram-bot
RUN pip install --no-cache-dir ./contracts ./telegram-bot

CMD ["python", "-m", "telegram_bot.main"]
