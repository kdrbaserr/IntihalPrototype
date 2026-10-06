from intihal_api.jobs.app import app
from intihal_api.jobs.runtime import dispatch_pending, run_async, run_stage


@app.task(name="intihal.healthcheck")
def healthcheck() -> dict[str, str]:
    """Exercise broker -> worker -> result backend without modifying business data."""
    return {"status": "ok"}


@app.task(name="intihal.documents.extract")
def extract(document_id: str) -> str:
    return run_async(run_stage(document_id, "extract"))


@app.task(name="intihal.analysis.run")
def analyze(document_id: str) -> str:
    return run_async(run_stage(document_id, "analyze"))


@app.task(name="intihal.dispatch_pending")
def dispatch() -> int:
    return run_async(
        dispatch_pending(lambda name, identifier: app.send_task(name, args=[identifier]))
    )
