import os

from celery import Celery

from ai_service.infra.tracing import setup_tracing

AI_TASK_QUEUE = "ai_tasks"
AI_BROKER_URL = "redis://valkey:6379/1"
setup_tracing(service_name=os.getenv("OTEL_SERVICE_NAME", "ai-service-celery"))

celery_app = Celery(
    "ai_service",
    broker=AI_BROKER_URL,
    include=["ai_service.app.tasks.pipeline"],
)

celery_app.conf.timezone = "UTC"
celery_app.conf.broker_url = AI_BROKER_URL
celery_app.conf.task_default_queue = AI_TASK_QUEUE
celery_app.conf.task_default_exchange = AI_TASK_QUEUE
celery_app.conf.task_default_routing_key = AI_TASK_QUEUE
celery_app.set_default()
