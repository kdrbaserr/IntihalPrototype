import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import select

from intihal_api.db.models import Analysis
from intihal_api.jobs.runtime import fail_document
from test_analyses_api import api


def test_retry_is_idempotent_delayed_bounded_and_keeps_failed_history():
    async def scenario():
        async with api() as (client, session, document, headers, _):
            created = await client.post(
                "/api/v1/analyses", json={"document_id": str(document.id)}, headers=headers
            )
            initial_id = created.json()["id"]
            current = await session.get(Analysis, UUID(initial_id))
            for _ in range(3):
                await session.refresh(document)
                await fail_document(document, current, session, "retry_exhausted")
                path = f"/api/v1/analyses/{current.id}/retry"
                before = datetime.now(UTC)
                retried = await client.post(path, headers=headers)
                assert retried.status_code == 202
                assert retried.json()["id"] != str(current.id)
                duplicate = await client.post(path, headers=headers)
                assert duplicate.json()["id"] == retried.json()["id"]
                await session.refresh(document)
                assert document.next_attempt_at.replace(tzinfo=UTC) >= before
                assert (document.next_attempt_at.replace(tzinfo=UTC) - before).total_seconds() >= 29
                assert document.processing_attempts == 0
                history = await client.get(f"/api/v1/analyses/{current.id}", headers=headers)
                assert history.json()["status"] == "failed"
                state = await client.get(f"/api/v1/documents/{document.id}", headers=headers)
                assert state.json()["latest_analysis_id"] == retried.json()["id"]
                current = await session.get(Analysis, UUID(retried.json()["id"]))
            await session.refresh(document)
            await fail_document(document, current, session, "processing_timeout")
            blocked = await client.post(f"/api/v1/analyses/{current.id}/retry", headers=headers)
            assert blocked.status_code == 409
            assert blocked.json()["detail"]["code"] == "analysis_retry_limit"
            stale = await client.post(f"/api/v1/analyses/{initial_id}/retry", headers=headers)
            assert stale.status_code == 409
            assert stale.json()["detail"]["code"] == "analysis_retry_conflict"
            start = await client.post(f"/api/v1/documents/{document.id}/analysis", headers=headers)
            assert start.json()["id"] == str(current.id)
            assert len(list(await session.scalars(select(Analysis)))) == 4

    asyncio.run(scenario())


@pytest.mark.parametrize("reason", ["ocr_required", "invalid_pdf", "stored_document_changed"])
def test_non_retryable_failure_needs_a_new_upload(reason):
    async def scenario():
        async with api() as (client, session, document, headers, _):
            created = await client.post(
                "/api/v1/analyses", json={"document_id": str(document.id)}, headers=headers
            )
            current = await session.get(Analysis, UUID(created.json()["id"]))
            await session.refresh(document)
            await fail_document(document, current, session, reason)
            result = await client.post(created.headers["Location"] + "/retry", headers=headers)
            assert result.status_code == 409
            assert result.json()["detail"]["code"] == "analysis_retry_not_allowed"
            assert len(list(await session.scalars(select(Analysis)))) == 1

    asyncio.run(scenario())


def test_retry_checks_ownership_and_requires_failed_run():
    async def scenario():
        async with api() as (client, _, document, headers, other):
            created = await client.post(
                "/api/v1/analyses", json={"document_id": str(document.id)}, headers=headers
            )
            path = created.headers["Location"] + "/retry"
            assert (await client.post(path, headers=other)).status_code == 404
            assert (await client.post(path)).status_code == 401
            active = await client.post(path, headers=headers)
            assert active.status_code == 409
            assert active.json()["detail"]["code"] == "analysis_retry_conflict"

    asyncio.run(scenario())
