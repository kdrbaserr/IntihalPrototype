import asyncio

from httpx import ASGITransport, AsyncClient, Response

from intihal_api.main import app


async def get(path: str) -> Response:
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(path)


def test_root_health_endpoint() -> None:
    response = asyncio.run(get("/health"))

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "Intihal Prototype API",
        "version": "0.1.0",
        "environment": "local",
    }


def test_versioned_health_endpoint() -> None:
    response = asyncio.run(get("/api/v1/health"))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
