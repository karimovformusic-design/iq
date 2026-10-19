FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production

WORKDIR /app

RUN groupadd --system mindora && useradd --system --gid mindora --home-dir /app mindora

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY mindora ./mindora
COPY migrations ./migrations
COPY alembic.ini entrypoint.sh ./

RUN chown -R mindora:mindora /app
USER mindora

EXPOSE 8080
CMD ["sh", "/app/entrypoint.sh"]
