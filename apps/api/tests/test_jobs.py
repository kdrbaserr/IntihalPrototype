from unittest.mock import patch

import pytest
from celery.contrib.testing.worker import start_worker
from celery.exceptions import QueueNotFound
from pydantic import ValidationError

from intihal_api.core.config import Settings
from intihal_api.jobs.app import (
    ANALYSIS_QUEUE,
    DEFAULT_QUEUE,
    DOCUMENTS_QUEUE,
    QUEUES,
    TransientJobError,
    create_celery_app,
)


def test_tasks_are_routed_to_declared_queues() -> None:
    app = create_celery_app(Settings(_env_file=None))
    try:
        router = app.amqp.Router()
        for task, expected in (
            ("intihal.documents.extract", DOCUMENTS_QUEUE),
            ("intihal.analysis.run", ANALYSIS_QUEUE),
            ("intihal.healthcheck", DEFAULT_QUEUE),
        ):
            assert router.route({}, task)["queue"].name == expected
        with pytest.raises(QueueNotFound):
            router.route({"queue": "misspelled"}, "intihal.healthcheck")
    finally:
        app.close()


def test_transient_failures_retry_with_backoff_then_stop() -> None:
    app = create_celery_app(Settings(_env_file=None, task_max_retries=3))
    app.conf.update(task_always_eager=True, task_store_eager_result=False)
    attempts = []

    @app.task(name="tests.transient")
    def failing():
        attempts.append(1)
        raise TransientJobError("temporary outage")

    try:
        # Deterministic jitter lets us inspect the actual retry countdowns.
        with patch("celery.utils.time.random.randrange", side_effect=lambda stop: stop - 1):
            with patch.object(failing, "retry", wraps=failing.retry) as retry:
                result = failing.apply()
        assert len(attempts) == 4  # initial attempt + 3 retries
        assert result.failed()
        assert isinstance(result.result, TransientJobError)
        assert [call.kwargs["countdown"] for call in retry.call_args_list] == [10, 20, 40, 80]
    finally:
        app.close()


def test_permanent_failure_is_not_retried() -> None:
    app = create_celery_app(Settings(_env_file=None))
    app.conf.update(task_always_eager=True, task_store_eager_result=False)
    attempts = []

    @app.task(name="tests.permanent")
    def failing():
        attempts.append(1)
        raise ValueError("invalid document")

    try:
        result = failing.apply()
        assert result.failed()
        assert len(attempts) == 1
    finally:
        app.close()


@pytest.mark.parametrize(
    "overrides",
    [
        {"task_soft_timeout_seconds": 300},
        {"redis_visibility_timeout_seconds": 420},
        {"task_retry_backoff_seconds": 121},
        {"redis_result_db": 0},
        {"task_max_retries": -1},
    ],
)
def test_invalid_worker_policies_are_rejected(overrides) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)


def test_redis_password_is_url_encoded_and_hidden_in_settings() -> None:
    settings = Settings(
        _env_file=None, redis_host="localhost", redis_port=6379,
        redis_broker_db=0, redis_result_db=1, redis_password="a@b:/?#%",
    )
    app = create_celery_app(settings)
    try:
        assert "a@b:/?#%" not in repr(settings)
        assert app.conf.broker_url == "redis://:a%40b%3A%2F%3F%23%25@localhost:6379/0"
        assert app.conf.result_backend == "redis://:a%40b%3A%2F%3F%23%25@localhost:6379/1"
    finally:
        app.close()


def test_worker_consumes_healthcheck_from_each_queue() -> None:
    """Exercise serialization, routing and consumption without external services."""
    app = create_celery_app(Settings(_env_file=None))
    app.conf.update(
        broker_url="memory://",
        result_backend="cache+memory://",
        task_always_eager=False,
    )
    app.loader.import_default_modules()
    try:
        with start_worker(app, pool="solo", queues=QUEUES, perform_ping_check=False):
            for queue in QUEUES:
                job = app.tasks["intihal.healthcheck"].apply_async(queue=queue)
                assert job.get(timeout=10) == {"status": "ok"}
    finally:
        app.close()
