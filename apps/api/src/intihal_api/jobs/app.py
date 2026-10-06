from urllib.parse import quote

from celery import Celery, Task
from kombu import Queue

from intihal_api.core.config import Settings, get_settings

DEFAULT_QUEUE = "intihal.default"
DOCUMENTS_QUEUE = "intihal.documents"
ANALYSIS_QUEUE = "intihal.analysis"
QUEUES = (DEFAULT_QUEUE, DOCUMENTS_QUEUE, ANALYSIS_QUEUE)


class TransientJobError(Exception):
    """An explicitly classified temporary failure that is safe to retry."""


def create_celery_app(settings: Settings | None = None) -> Celery:
    settings = settings or get_settings()
    password = quote(settings.redis_password.get_secret_value(), safe="")
    redis_base = f"redis://:{password}@{settings.redis_host}:{settings.redis_port}"

    class RetryingTask(Task):
        autoretry_for = (TransientJobError,)
        max_retries = settings.task_max_retries
        retry_backoff = settings.task_retry_backoff_seconds
        retry_backoff_max = settings.task_retry_backoff_max_seconds
        retry_jitter = True

    app = Celery(
        "intihal",
        broker=f"{redis_base}/{settings.redis_broker_db}",
        backend=f"{redis_base}/{settings.redis_result_db}",
        task_cls=RetryingTask,
        include=["intihal_api.jobs.tasks"],
    )
    app.conf.update(
        task_queues=tuple(Queue(name, routing_key=name) for name in QUEUES),
        task_default_queue=DEFAULT_QUEUE,
        task_default_routing_key=DEFAULT_QUEUE,
        task_create_missing_queues=False,
        task_routes={
            "intihal.documents.*": {"queue": DOCUMENTS_QUEUE},
            "intihal.analysis.*": {"queue": ANALYSIS_QUEUE},
            "intihal.healthcheck": {"queue": DEFAULT_QUEUE},
        },
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_track_started=True,
        task_soft_time_limit=settings.task_soft_timeout_seconds,
        task_time_limit=settings.task_hard_timeout_seconds,
        # Business jobs must be idempotent before opting in to late acknowledgment.
        task_acks_late=False,
        task_reject_on_worker_lost=False,
        worker_prefetch_multiplier=1,
        worker_concurrency=settings.worker_concurrency,
        worker_pool="prefork",
        broker_connection_timeout=5,
        broker_connection_retry_on_startup=True,
        broker_connection_max_retries=10,
        broker_transport_options={
            "visibility_timeout": settings.redis_visibility_timeout_seconds,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
        },
        result_backend_transport_options={
            "visibility_timeout": settings.redis_visibility_timeout_seconds,
            "global_keyprefix": "intihal:",
        },
        visibility_timeout=settings.redis_visibility_timeout_seconds,
        redis_socket_connect_timeout=5,
        redis_socket_timeout=5,
        task_publish_retry=True,
        task_publish_retry_policy={
            "max_retries": 3,
            "interval_start": 0,
            "interval_step": 0.5,
            "interval_max": 2,
        },
        result_expires=settings.task_result_expires_seconds,
        timezone="UTC",
        enable_utc=True,
    )
    return app


app = create_celery_app()
