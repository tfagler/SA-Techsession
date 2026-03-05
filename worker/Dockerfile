FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY api /app

CMD ["celery", "-A", "app.celery_app.celery_app", "worker", "--loglevel=info", "-Q", "ingest"]
