import asyncio
import json
import traceback
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from intihal_api.api.analysis_schemas import AnalysisResponse
from intihal_api.core.diagnostics import request_id
from intihal_api.core.errors import PUBLIC_MESSAGES
from intihal_api.jobs.app import TransientJobError
from intihal_api.jobs.runtime import run_async
from intihal_api.main import create_app

SECRET = "private-password-and-document-content"


def diagnostic_records(caplog):
    return [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "intihal_api.core.diagnostics"
    ]


def test_unhandled_error_is_safe_correlated_and_cors_readable(caplog):
    application = create_app()
    application.debug = True  # middleware must remain safe even when debug is changed

    @application.get("/crash")
    async def crash():
        try:
            raise ValueError(SECRET)
        except ValueError as cause:
            raise RuntimeError(SECRET) from cause

    async def scenario():
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            responses = await asyncio.gather(
                *[
                    client.get(
                        "/crash",
                        params={"secret": SECRET},
                        headers={"Origin": "http://localhost:3000", "X-Request-ID": SECRET},
                    )
                    for _ in range(2)
                ]
            )
        assert request_id.get() is None
        assert len({r.headers["X-Request-ID"] for r in responses}) == 2
        for response in responses:
            assert response.status_code == 500
            detail = response.json()["detail"]
            assert detail["code"] == "internal_error"
            assert detail["message"] == PUBLIC_MESSAGES["internal_error"]
            assert detail["trace_id"] == response.headers["X-Request-ID"]
            assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
            assert "X-Request-ID" in response.headers["Access-Control-Expose-Headers"]
            assert SECRET not in response.text
            record = next(
                r for r in diagnostic_records(caplog) if r["trace_id"] == detail["trace_id"]
            )
            assert record["route"] == "/crash"
            assert [e["exception_type"] for e in record["trace"]] == [
                "builtins.RuntimeError",
                "builtins.ValueError",
            ]
            assert any(f["function"] == "crash" for f in record["trace"][0]["frames"])
            assert all(f["line"] > 0 and f["file"] for f in record["trace"][0]["frames"])
        assert SECRET not in caplog.text

    asyncio.run(scenario())


def test_handled_errors_validation_and_missing_routes_share_safe_contract(caplog):
    application = create_app()

    @application.get("/denied")
    async def denied():
        raise HTTPException(
            401,
            detail={"code": "authentication_required", "message": SECRET},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @application.get("/validate")
    async def validate(count: int):
        return {"count": count}

    @application.get("/unknown-code")
    async def unknown_code():
        raise HTTPException(400, detail={"code": SECRET, "message": SECRET})

    async def scenario():
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            cases = [
                ("/denied", 401, "authentication_required"),
                (f"/validate?count={SECRET}", 422, "validation_error"),
                ("/missing", 404, "not_found"),
                ("/unknown-code", 400, "invalid_request"),
            ]
            for path, status, code in cases:
                response = await client.get(path)
                assert response.status_code == status
                assert response.json()["detail"]["code"] == code
                assert response.json()["detail"]["trace_id"] == response.headers["X-Request-ID"]
                assert SECRET not in response.text
                if status == 401:
                    assert response.headers["WWW-Authenticate"] == "Bearer"
        assert SECRET not in caplog.text
        assert request_id.get() is None

    asyncio.run(scenario())


@pytest.mark.parametrize("transient", [False, True])
def test_worker_logs_original_trace_but_raises_safe_exception(caplog, transient):
    async def failing_operation():
        if transient:
            raise OperationalError(f"SELECT {SECRET}", {"password": SECRET}, ValueError(SECRET))
        raise ValueError(SECRET)

    expected = TransientJobError if transient else RuntimeError
    with pytest.raises(expected) as caught:
        run_async(failing_operation(), task_id="task-123", stage="extract", document_id="doc-123")
    record = diagnostic_records(caplog)[0]
    assert record["task_id"] == "task-123"
    assert record["stage"] == "extract"
    assert record["document_id"] == "doc-123"
    assert record["trace_id"] in str(caught.value)
    assert any(f["function"] == "failing_operation" for f in record["trace"][0]["frames"])
    assert SECRET not in caplog.text
    assert SECRET not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__suppress_context__


def test_old_failure_messages_are_filtered_from_analysis_responses():
    values = {
        "id": uuid4(),
        "document_id": uuid4(),
        "status": "failed",
        "algorithm_version": "v1",
        "started_at": None,
        "completed_at": None,
        "failure_reason": SECRET,
    }
    assert AnalysisResponse(**values).failure_reason == "processing_failed"
    values["failure_reason"] = "processing_timeout"
    assert AnalysisResponse(**values).failure_reason == "processing_timeout"
