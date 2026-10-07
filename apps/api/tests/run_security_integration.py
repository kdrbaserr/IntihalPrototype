"""Run real security tests in newly-created disposable PostgreSQL/MinIO resources."""

import asyncio
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
from sqlalchemy.engine import make_url

from intihal_api.core.config import get_settings
from intihal_api.storage import create_object_storage_service

API_DIR = Path(__file__).resolve().parents[1]


async def main() -> int:
    suffix = uuid4().hex
    database = f"intihal_security_test_{suffix}"
    bucket = f"intihal-security-test-{suffix}"
    assert re.fullmatch(r"intihal_security_test_[0-9a-f]{32}", database)
    assert re.fullmatch(r"intihal-security-test-[0-9a-f]{32}", bucket)
    settings = get_settings()
    base_url = make_url(settings.database_url)
    test_url = base_url.set(database=database)
    admin_url = base_url.set(drivername="postgresql", database="postgres")
    storage = create_object_storage_service(settings.model_copy(update={"minio_bucket": bucket}))
    connection = await asyncpg.connect(admin_url.render_as_string(hide_password=False))
    created_database = created_bucket = False
    try:
        if storage.client.bucket_exists(bucket):
            raise RuntimeError("Refusing to use an existing test bucket")
        await connection.execute(f'CREATE DATABASE "{database}"')
        created_database = True
        storage.client.make_bucket(bucket)
        created_bucket = True
        environment = os.environ.copy()
        environment["INTIHAL_SECURITY_TEST_DATABASE_URL"] = test_url.render_as_string(
            hide_password=False
        )
        environment["INTIHAL_SECURITY_TEST_MINIO_BUCKET"] = bucket
        print("Created isolated PostgreSQL database and MinIO bucket.", flush=True)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_security_integration.py",
                "-o",
                "addopts=",
                "-q",
            ],
            cwd=API_DIR,
            env=environment,
            check=False,
        )
        return result.returncode
    finally:
        try:
            # Names were generated above; cleanup is restricted to resources we created.
            if created_bucket:
                for item in storage.client.list_objects(bucket, recursive=True):
                    storage.client.remove_object(bucket, item.object_name)
                storage.client.remove_bucket(bucket)
                assert not storage.client.bucket_exists(bucket)
        finally:
            try:
                if created_database:
                    await connection.execute(f'DROP DATABASE "{database}" WITH (FORCE)')
                    assert (
                        await connection.fetchval(
                            "SELECT datname FROM pg_database WHERE datname = $1", database
                        )
                        is None
                    )
            finally:
                await connection.close()
        print("Removed isolated test database and bucket.", flush=True)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
