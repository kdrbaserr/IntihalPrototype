import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from auth_helpers import session_headers
from intihal_api.core.config import Settings
from intihal_api.db.models import Analysis, DocumentChunk, DocumentStatus, Match, SourceChunk, User
from intihal_api.db.session import get_db_session
from intihal_api.jobs.runtime import fail_document
from intihal_api.jobs.workflow import analyze_document, extract_document
from intihal_api.main import create_app
from test_document_workflow import CONTENT, StoredContent, database, seed_source


@asynccontextmanager
async def api():
    async with database() as (session, document, factory):
        other = User(id=uuid4(), email="other@api.test", display_name="Other")
        session.add(other)
        await session.commit()
        application = create_app()

        async def override_session():
            async with factory() as request_session:
                yield request_session

        application.dependency_overrides[get_db_session] = override_session
        async with AsyncClient(
            transport=ASGITransport(app=application), base_url="http://test"
        ) as client:
            yield (
                client,
                session,
                document,
                await session_headers(session, document.owner_id),
                await session_headers(session, other.id),
            )


def test_create_status_and_existing_document_route_share_the_same_run():
    async def scenario():
        async with api() as (client, session, document, headers, _):
            created = await client.post(
                "/api/v1/analyses", json={"document_id": str(document.id)}, headers=headers
            )
            assert created.status_code == 202
            identifier = created.json()["id"]
            assert created.json()["status"] == "queued"
            assert created.headers["Location"] == f"/api/v1/analyses/{identifier}"
            repeated = await client.post(
                "/api/v1/analyses", json={"document_id": str(document.id)}, headers=headers
            )
            legacy = await client.post(f"/api/v1/documents/{document.id}/analysis", headers=headers)
            assert repeated.json()["id"] == legacy.json()["id"] == identifier
            assert len(list(await session.scalars(select(Analysis)))) == 1
            detail = await client.get(created.headers["Location"], headers=headers)
            assert detail.status_code == 200
            assert detail.json()["document_status"] == "queued"
            assert (
                detail.json()["config_snapshot"]["algorithm_version"]
                == created.json()["algorithm_version"]
            )
            pending = await client.get(f"/api/v1/analyses/{identifier}/matches", headers=headers)
            assert pending.status_code == 409
            assert pending.json()["detail"]["code"] == "analysis_not_completed"

    asyncio.run(scenario())


def test_matches_include_paginated_evidence_and_correct_global_offsets():
    async def scenario():
        async with api() as (client, session, document, headers, _):
            await seed_source(session)
            await seed_source(session)
            created = await client.post(
                "/api/v1/analyses", json={"document_id": str(document.id)}, headers=headers
            )
            identifier = created.json()["id"]
            analysis = await session.get(Analysis, UUID(identifier))
            await session.refresh(document)
            await extract_document(document, analysis, session, StoredContent())
            await analyze_document(document, analysis, session, Settings(_env_file=None))
            matches = list(await session.scalars(select(Match)))
            # Evidence offsets are global; chunk text starts at a non-zero offset.
            chunk = await session.get(DocumentChunk, matches[0].document_chunk_id)
            chunk.char_start += 100
            chunk.char_end += 100
            chunk.page_number = 2
            for match in matches:
                match.document_match_start += 100
                match.document_match_end += 100
                source = await session.get(SourceChunk, match.source_chunk_id)
                source.char_start += 200
                source.char_end += 200
                source.page_number = 5
                match.source_match_start += 200
                match.source_match_end += 200
            await session.commit()
            url = f"/api/v1/analyses/{identifier}/matches"
            full = (await client.get(url, headers=headers)).json()
            assert full["total"] == 2
            assert len(full["items"]) == 2
            assert full["offset_unit"] == "unicode_code_points"
            assert full["range_convention"] == "start_inclusive_end_exclusive"
            for item in full["items"]:
                assert item["document"]["text"] == item["source"]["text"] == CONTENT[:-1]
                assert item["document"]["char_start"] == 100
                assert item["source"]["char_start"] == 200
                assert item["source"]["license_name"] == "CC0"
                assert item["similarity_score"] == "1.0000"
                assert item["document"]["page_number"] == 2
                assert item["source"]["page_number"] == 5
                assert item["source"]["original_filename"] == "source.txt"
                components = item["score_components"]
                assert components["scope"] == "chunk_pair"
                assert components["algorithm_version"] == analysis.algorithm_version
                for signal, weight in (
                    ("word_tfidf", "0.50"),
                    ("character_tfidf", "0.25"),
                    ("word_overlap", "0.25"),
                ):
                    assert Decimal(components[signal]["score"]) == 1
                    assert Decimal(components[signal]["weight"]) == Decimal(weight)
                    assert Decimal(components[signal]["contribution"]) == Decimal(weight)
                assert "storage_key" not in item["source"]
            first = (await client.get(url + "?limit=1", headers=headers)).json()
            second = (await client.get(url + "?limit=1&offset=1", headers=headers)).json()
            assert first["items"][0]["id"] == full["items"][0]["id"]
            assert second["items"][0]["id"] == full["items"][1]["id"]
            assert (await client.get(url + "?offset=100", headers=headers)).json()["items"] == []
            assert (await client.get(created.headers["Location"], headers=headers)).json()[
                "status"
            ] == "completed"

    asyncio.run(scenario())


def test_components_preserve_snapshot_and_unicode_ranges_without_recalculation(monkeypatch):
    async def scenario():
        async with api() as (client, session, document, headers, _):
            await seed_source(session)
            created = await client.post(
                "/api/v1/analyses", json={"document_id": str(document.id)}, headers=headers
            )
            analysis = await session.get(Analysis, UUID(created.json()["id"]))
            await session.refresh(document)
            await extract_document(document, analysis, session, StoredContent())
            chunk = await session.scalar(select(DocumentChunk))
            chunk.content = "😀 " + chunk.content + " Yeni bağımsız açıklamalar eklendi."
            chunk.char_end = len(chunk.content)
            analysis.similarity_threshold = Decimal("0")
            analysis.config_snapshot = {
                **analysis.config_snapshot,
                "similarity_threshold": "0",
                "word_tfidf_weight": "0.10",
                "character_tfidf_weight": "0.20",
                "word_overlap_weight": "0.70",
            }
            await session.commit()
            await analyze_document(document, analysis, session, Settings(_env_file=None))

            def unexpected_recalculation(*args, **kwargs):
                pytest.fail("GET must read persisted signals without recalculating")

            monkeypatch.setattr(
                "intihal_api.jobs.workflow.calculate_hybrid_similarity", unexpected_recalculation
            )
            result = await client.get(created.headers["Location"] + "/matches", headers=headers)
            assert result.status_code == 200
            item = result.json()["items"][0]
            assert (
                item["document"]["char_start"] == 2
            )  # emoji is one code point, not two UTF-16 units
            assert (
                chunk.content[item["document"]["char_start"] : item["document"]["char_end"]]
                == (item["document"]["text"])
            )
            assert item["document"]["page_number"] is None
            assert item["source"]["page_number"] is None
            components = item["score_components"]
            total = Decimal(0)
            for signal, weight in (
                ("word_tfidf", "0.10"),
                ("character_tfidf", "0.20"),
                ("word_overlap", "0.70"),
            ):
                value = components[signal]
                assert Decimal(value["weight"]) == Decimal(weight)
                assert Decimal(value["contribution"]) == Decimal(value["score"]) * Decimal(weight)
                assert 0 <= Decimal(value["score"]) < 1
                total += Decimal(value["contribution"])
            assert total.quantize(Decimal("0.0001")) == Decimal(item["similarity_score"])
            # Existing matches without stored components remain readable.
            stored = await session.scalar(select(Match))
            stored.score_components = None
            await session.commit()
            legacy = await client.get(created.headers["Location"] + "/matches", headers=headers)
            assert legacy.status_code == 200
            assert legacy.json()["items"][0]["score_components"] is None
            assert legacy.json()["items"][0]["document"] == item["document"]

    asyncio.run(scenario())


def test_completed_analysis_with_no_matches_returns_an_empty_successful_page():
    async def scenario():
        async with api() as (client, session, document, headers, _):
            created = await client.post(
                "/api/v1/analyses", json={"document_id": str(document.id)}, headers=headers
            )
            analysis = await session.get(Analysis, UUID(created.json()["id"]))
            await session.refresh(document)
            await extract_document(document, analysis, session, StoredContent())
            await analyze_document(document, analysis, session, Settings(_env_file=None))
            result = await client.get(f"/api/v1/analyses/{analysis.id}/matches", headers=headers)
            assert result.status_code == 200
            assert result.json()["total"] == 0
            assert result.json()["items"] == []

    asyncio.run(scenario())


def test_analysis_routes_hide_other_users_and_deleted_documents():
    async def scenario():
        async with api() as (client, session, document, headers, other):
            body = {"document_id": str(document.id)}
            assert (await client.post("/api/v1/analyses", json=body)).status_code == 401
            assert (
                await client.post("/api/v1/analyses", json=body, headers=other)
            ).status_code == 404
            result = await client.post("/api/v1/analyses", json=body, headers=headers)
            url = result.headers["Location"]
            for path in (url, url + "/matches"):
                assert (await client.get(path)).status_code == 401
                assert (await client.get(path, headers=other)).status_code == 404
                assert (
                    await client.get(
                        path.replace(result.json()["id"], str(uuid4())), headers=headers
                    )
                ).status_code == 404
            await session.refresh(document)
            document.status = DocumentStatus.DELETED
            await session.commit()
            assert (await client.get(url, headers=headers)).status_code == 404
            assert (await client.get(url + "/matches", headers=headers)).status_code == 404
            assert (
                await client.post("/api/v1/analyses", json=body, headers=headers)
            ).status_code == 404

    asyncio.run(scenario())


def test_failed_run_keeps_its_status_when_the_document_is_requeued():
    async def scenario():
        async with api() as (client, session, document, headers, _):
            body = {"document_id": str(document.id)}
            created = await client.post("/api/v1/analyses", json=body, headers=headers)
            original = await session.get(Analysis, UUID(created.json()["id"]))
            await session.refresh(document)
            await fail_document(document, original, session, "processing_failed")
            repeated = await client.post("/api/v1/analyses", json=body, headers=headers)
            assert repeated.json()["id"] == created.json()["id"]
            new = await client.post(created.headers["Location"] + "/retry", headers=headers)
            assert new.json()["id"] != created.json()["id"]
            history = (await client.get(created.headers["Location"], headers=headers)).json()
            assert history["status"] == "failed"
            assert history["failure_reason"] == "processing_failed"
            assert history["document_status"] == "queued"
            assert (
                await client.get(created.headers["Location"] + "/matches", headers=headers)
            ).status_code == 409

    asyncio.run(scenario())


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
def test_invalid_pagination_is_rejected(query):
    async def scenario():
        async with api() as (client, _, document, headers, _):
            created = await client.post(
                "/api/v1/analyses", json={"document_id": str(document.id)}, headers=headers
            )
            result = await client.get(
                created.headers["Location"] + "/matches?" + query, headers=headers
            )
            assert result.status_code == 422

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "body", [{}, {"document_id": "invalid"}, {"document_id": str(uuid4()), "status": "completed"}]
)
def test_invalid_create_payload_is_rejected(body):
    async def scenario():
        async with api() as (client, _, _, headers, _):
            assert (
                await client.post("/api/v1/analyses", json=body, headers=headers)
            ).status_code == 422

    asyncio.run(scenario())
