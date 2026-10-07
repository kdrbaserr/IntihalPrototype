"""Owner boundaries must hold for every public document/analysis/report query."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from intihal_api.core.config import Settings
from intihal_api.db.models import Document, DocumentChunk, DocumentStatus, Match, User, UserRole
from intihal_api.jobs.workflow import analyze_document, extract_document
from test_analyses_api import api
from test_document_workflow import StoredContent, seed_source


def another_document(owner_id):
    return Document(
        owner_id=owner_id,
        original_filename="private-other-document.txt",
        content_type="text/plain",
        size_bytes=10,
        sha256="a" * 64,
        storage_bucket="intihal-documents",
        storage_key=f"private/{uuid4()}",
        status=DocumentStatus.UPLOADED,
    )


@pytest.mark.parametrize("other_role", [UserRole.USER, UserRole.ADMIN])
def test_all_resource_endpoints_require_the_owner_even_for_admins(other_role):
    async def scenario():
        async with api() as (client, session, document, owner_headers, other_headers):
            other = await session.scalar(select(User).where(User.email == "other@api.test"))
            other.role = other_role
            foreign_document = another_document(other.id)
            session.add(foreign_document)
            await session.commit()
            body = {"document_id": str(document.id)}
            created = await client.post("/api/v1/analyses", json=body, headers=owner_headers)
            assert created.status_code == 202
            doc_url = f"/api/v1/documents/{document.id}"
            analysis_url = created.headers["Location"]
            operations = [
                ("GET", doc_url, None),
                ("POST", doc_url + "/analysis", None),
                ("POST", "/api/v1/analyses", body),
                ("GET", analysis_url, None),
                ("GET", analysis_url + "/matches?limit=1&offset=0", None),
                ("POST", analysis_url + "/retry", None),
            ]
            for method, url, payload in operations:
                anonymous = await client.request(method, url, json=payload)
                assert anonymous.status_code == 401, (method, url, anonymous.text)
                denied = await client.request(method, url, headers=other_headers, json=payload)
                assert denied.status_code == 404, (method, url, denied.text)
                assert str(document.owner_id) not in denied.text

            assert (await client.get(doc_url, headers=owner_headers)).status_code == 200
            assert (await client.get(analysis_url, headers=owner_headers)).status_code == 200
            listed = await client.get("/api/v1/documents?limit=1&offset=0", headers=other_headers)
            assert [row["id"] for row in listed.json()] == [str(foreign_document.id)]
            # Query parameters cannot override the authenticated owner.
            owner_list = await client.get(
                f"/api/v1/documents?owner_id={other.id}",
                headers=owner_headers,
            )
            assert [row["id"] for row in owner_list.json()] == [str(document.id)]
            assert (
                await client.get("/api/v1/documents?offset=1", headers=owner_headers)
            ).json() == []

            await session.refresh(document)
            document.status = DocumentStatus.DELETED
            await session.commit()
            assert (await client.get("/api/v1/documents", headers=owner_headers)).json() == []
            for method, url, payload in operations:
                deleted = await client.request(method, url, headers=owner_headers, json=payload)
                assert deleted.status_code == 404, (method, url, deleted.text)

    asyncio.run(scenario())


@pytest.mark.parametrize("same_owner", [False, True])
def test_report_count_and_evidence_exclude_chunks_from_another_document(same_owner):
    async def scenario():
        async with api() as (client, session, document, headers, _):
            await seed_source(session)
            created = await client.post(
                "/api/v1/analyses", headers=headers, json={"document_id": str(document.id)}
            )
            from intihal_api.db.models import Analysis

            analysis = await session.get(Analysis, UUID(created.json()["id"]))
            await session.refresh(document)
            await extract_document(document, analysis, session, StoredContent())
            await analyze_document(document, analysis, session, Settings(_env_file=None))
            url = f"/api/v1/analyses/{analysis.id}/matches"
            valid = await client.get(url, headers=headers)
            assert valid.status_code == 200 and valid.json()["total"] == 1

            other = await session.scalar(select(User).where(User.email == "other@api.test"))
            foreign_document = another_document(document.owner_id if same_owner else other.id)
            session.add(foreign_document)
            await session.flush()
            foreign_chunk = DocumentChunk(
                document_id=foreign_document.id,
                chunk_index=0,
                content="PRIVATE TEXT FROM A DIFFERENT DOCUMENT",
                char_start=0,
                char_end=38,
                token_count=7,
                content_sha256="b" * 64,
            )
            session.add(foreign_chunk)
            await session.flush()
            match = await session.scalar(select(Match).where(Match.analysis_id == analysis.id))
            # The database permits independent foreign keys; the API must not expose this row.
            match.document_chunk_id = foreign_chunk.id
            await session.commit()
            for query in ("", "?limit=1&offset=0", "?limit=1&offset=100"):
                result = await client.get(url + query, headers=headers)
                assert result.status_code == 200
                assert result.json()["total"] == 0
                assert result.json()["items"] == []
                assert "PRIVATE TEXT" not in result.text

    asyncio.run(scenario())


def test_queries_follow_the_document_owner_in_the_database():
    async def scenario():
        async with api() as (client, session, document, headers, other_headers):
            created = await client.post(
                "/api/v1/analyses", headers=headers, json={"document_id": str(document.id)}
            )
            assert created.status_code == 202
            other = await session.scalar(select(User).where(User.email == "other@api.test"))
            await session.refresh(document)
            document.owner_id = other.id
            await session.commit()
            doc_url = f"/api/v1/documents/{document.id}"
            analysis_url = created.headers["Location"]
            for url in (doc_url, analysis_url, analysis_url + "/matches"):
                assert (await client.get(url, headers=headers)).status_code == 404
            transferred = await client.get(doc_url, headers=other_headers)
            assert transferred.status_code == 200
            assert transferred.json()["latest_analysis_id"] == created.json()["id"]
            assert (await client.get(analysis_url, headers=other_headers)).status_code == 200
            assert (await client.get("/api/v1/documents", headers=headers)).json() == []

    asyncio.run(scenario())
