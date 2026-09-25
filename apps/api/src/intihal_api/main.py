from fastapi import FastAPI

from intihal_api.api.health import router as health_router
from intihal_api.core.config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    # `/health` is convenient for local checks; the versioned path is the
    # stable contract consumed by Docker and future clients.
    application.include_router(health_router, include_in_schema=False)
    application.include_router(health_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()
