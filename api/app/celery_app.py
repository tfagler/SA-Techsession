from celery import Celery
from app.config import get_settings


settings = get_settings()
celery_app = Celery(
    'worker',
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['app.tasks'],
)
celery_app.conf.task_routes = {'app.tasks.ingest_session_task': {'queue': 'ingest'}}
