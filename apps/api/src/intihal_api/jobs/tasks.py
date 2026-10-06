from intihal_api.jobs.app import app


@app.task(name="intihal.healthcheck")
def healthcheck() -> dict[str, str]:
    """Exercise broker -> worker -> result backend without modifying business data."""
    return {"status": "ok"}
