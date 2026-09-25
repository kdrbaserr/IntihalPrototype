from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from intihal_api.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Return a lightweight liveness response for users and containers."""

    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
