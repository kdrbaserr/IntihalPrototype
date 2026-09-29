from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from collections.abc import Coroutine, Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy.engine import make_url

API_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_ENV = "INTIHAL_TEST_DATABASE_URL"

EXPECTED_TABLES = {
    "users",
    "documents",
    "source_documents",
    "source_chunks",
    "document_chunks",
    "analyses",
    "matches",
}
EXPECTED_ENUMS = {
    "user_status",
    "document_status",
    "source_document_status",
    "license_status",
    "analysis_status",
    "match_method",
}


def run_async[T](coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


def require_test_database_url() -> str:
    database_url = os.getenv(TEST_DATABASE_ENV)
    if database_url is None:
        pytest.skip(f"{TEST_DATABASE_ENV} is not configured")

    parsed_url = make_url(database_url)
    database_name = parsed_url.database or ""
    if "test" not in database_name.lower():
        pytest.fail(
            f"Refusing destructive migration test against non-test database: {database_name!r}"
        )
    return database_url


def asyncpg_url(database_url: str) -> str:
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)


def run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["INTIHAL_DATABASE_URL"] = database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=API_DIR,
        env=environment,
        check=True,
    )


async def fetch_public_object_names(database_url: str) -> tuple[set[str], set[str]]:
    connection = await asyncpg.connect(asyncpg_url(database_url))
    try:
        tables = await connection.fetch(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename <> 'alembic_version'
            """
        )
        enums = await connection.fetch(
            """
            SELECT type.typname
            FROM pg_type AS type
            JOIN pg_namespace AS namespace ON namespace.oid = type.typnamespace
            WHERE namespace.nspname = 'public'
              AND type.typtype = 'e'
            """
        )
        return (
            {record["tablename"] for record in tables},
            {record["typname"] for record in enums},
        )
    finally:
        await connection.close()


async def fetch_required_source_columns(database_url: str) -> set[str]:
    connection = await asyncpg.connect(asyncpg_url(database_url))
    try:
        rows = await connection.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'source_documents'
              AND is_nullable = 'NO'
            """
        )
        return {row["column_name"] for row in rows}
    finally:
        await connection.close()


@pytest.fixture
def migrated_database_url() -> Iterator[str]:
    database_url = require_test_database_url()
    run_alembic(database_url, "downgrade", "base")
    run_alembic(database_url, "upgrade", "head")
    try:
        yield database_url
    finally:
        run_alembic(database_url, "downgrade", "base")


def test_migration_upgrades_and_downgrades_complete_schema() -> None:
    database_url = require_test_database_url()
    run_alembic(database_url, "downgrade", "base")

    try:
        run_alembic(database_url, "upgrade", "head")
        run_alembic(database_url, "check")
        tables, enums = run_async(fetch_public_object_names(database_url))
        assert tables == EXPECTED_TABLES
        assert enums == EXPECTED_ENUMS
    finally:
        run_alembic(database_url, "downgrade", "base")

    tables, enums = run_async(fetch_public_object_names(database_url))
    assert tables == set()
    assert enums == set()


async def insert_document_with_missing_owner(database_url: str) -> None:
    connection = await asyncpg.connect(asyncpg_url(database_url))
    try:
        with pytest.raises(asyncpg.ForeignKeyViolationError):
            await connection.execute(
                """
                INSERT INTO documents (
                    id, owner_id, original_filename, content_type, size_bytes,
                    sha256, storage_bucket, storage_key
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                uuid4(),
                uuid4(),
                "orphan.txt",
                "text/plain",
                10,
                "a" * 64,
                "documents",
                "orphan.txt",
            )
    finally:
        await connection.close()


def test_foreign_key_rejects_document_without_owner(migrated_database_url: str) -> None:
    run_async(insert_document_with_missing_owner(migrated_database_url))


def test_source_identity_license_and_checksum_are_required(
    migrated_database_url: str,
) -> None:
    required_columns = run_async(fetch_required_source_columns(migrated_database_url))

    assert {
        "title",
        "license_name",
        "license_evidence_reference",
        "sha256",
    } <= required_columns


async def insert_duplicate_source_hash(database_url: str) -> None:
    connection = await asyncpg.connect(asyncpg_url(database_url))
    try:
        statement = """
            INSERT INTO source_documents (
                id, title, license_name, rights_holder, license_evidence_reference,
                original_filename, content_type, size_bytes, sha256, storage_bucket, storage_key
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """
        checksum = "b" * 64
        await connection.execute(
            statement,
            uuid4(),
            "Birinci kaynak",
            "CC BY 4.0",
            "Örnek Hak Sahibi",
            "LISANS-KANIT-001",
            "birinci.txt",
            "text/plain",
            100,
            checksum,
            "sources",
            "birinci.txt",
        )

        with pytest.raises(asyncpg.UniqueViolationError):
            await connection.execute(
                statement,
                uuid4(),
                "İkinci kaynak",
                "CC BY 4.0",
                "Örnek Hak Sahibi",
                "LISANS-KANIT-002",
                "ikinci.txt",
                "text/plain",
                100,
                checksum,
                "sources",
                "ikinci.txt",
            )
    finally:
        await connection.close()


def test_source_document_hash_is_unique(migrated_database_url: str) -> None:
    run_async(insert_duplicate_source_hash(migrated_database_url))


async def insert_invalid_user_status(database_url: str) -> None:
    connection = await asyncpg.connect(asyncpg_url(database_url))
    try:
        with pytest.raises(asyncpg.InvalidTextRepresentationError):
            await connection.execute(
                """
                INSERT INTO users (id, email, display_name, status)
                VALUES ($1, $2, $3, $4)
                """,
                uuid4(),
                "enum-test@example.com",
                "Enum Test",
                "unknown-status",
            )
    finally:
        await connection.close()


def test_enum_rejects_unknown_status(migrated_database_url: str) -> None:
    run_async(insert_invalid_user_status(migrated_database_url))
