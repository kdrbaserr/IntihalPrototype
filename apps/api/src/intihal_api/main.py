import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.concurrency import run_in_threadpool

from intihal_api.api.health import router as health_router
from intihal_api.core.config import get_settings
from intihal_api.storage import ObjectStorageService, create_object_storage_service

logger = logging.getLogger(__name__)


def create_app(storage_service: ObjectStorageService | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    storage = storage_service or create_object_storage_service(settings)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        # The SDK is synchronous, so its network call runs outside the async event
        # loop.  The API does not accept traffic until storage is actually usable.
        logger.info("Ensuring object-storage bucket exists", extra={"bucket": storage.bucket_name})
        await run_in_threadpool(storage.ensure_bucket)
        application.state.storage = storage
        yield

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # `/health` is convenient for local checks; the versioned path is the
    # stable contract consumed by Docker and future clients.
    application.include_router(health_router, include_in_schema=False)
    application.include_router(health_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()
