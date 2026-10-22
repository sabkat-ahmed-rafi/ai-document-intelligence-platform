from celery import Celery
from core.config import settings

celery_app = Celery(
    "ai_document_intelligence",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["modules.processing.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_acks_late=True,  # Guarantees no lost tasks if worker crashes mid-processing
    task_reject_on_worker_lost=True,  # Re-queues task if worker process terminates
    worker_prefetch_multiplier=1,  # Fair distribution: don't hoard heavy document tasks
)
