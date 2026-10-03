FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/database.sqlite \
    BACKUP_PATH=/data/backups

WORKDIR /app

RUN useradd --create-home --uid 10001 bot
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=bot:bot . /app
RUN mkdir -p /data/backups && chown -R bot:bot /data

USER bot
CMD ["python", "main.py"]
