from intihal_api.jobs.app import app
from intihal_api.jobs.runtime import dispatch_pending, run_async, run_retention_cleanup, run_stage


@app.task(name="intihal.cleanup_expired_documents")
def cleanup_expired() -> int:
    return run_async(run_retention_cleanup(), stage="retention_cleanup")


@app.task(name="intihal.healthcheck")
def healthcheck() -> dict[str, str]:
    """Exercise broker -> worker -> result backend without modifying business data."""
    return {"status": "ok"}


@app.task(name="intihal.documents.extract", bind=True)
def extract(self, document_id: str) -> str:
    return run_async(
        run_stage(document_id, "extract", task_id=self.request.id),
        document_id=document_id,
        stage="extract",
        task_id=self.request.id,
    )


@app.task(name="intihal.analysis.run", bind=True)
def analyze(self, document_id: str) -> str:
    return run_async(
        run_stage(document_id, "analyze", task_id=self.request.id),
        document_id=document_id,
        stage="analyze",
        task_id=self.request.id,
    )


@app.task(name="intihal.dispatch_pending", bind=True)
def dispatch(self) -> int:
    return run_async(
        dispatch_pending(lambda name, identifier: self.app.send_task(name, args=[identifier])),
        task_id=self.request.id,
        stage="dispatch",
    )
