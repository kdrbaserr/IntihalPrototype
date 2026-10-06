from intihal_api.db.models import Document, DocumentStatus

TRANSITIONS = {
    DocumentStatus.UPLOADED: {DocumentStatus.QUEUED},
    DocumentStatus.QUEUED: {DocumentStatus.EXTRACTING, DocumentStatus.FAILED},
    DocumentStatus.EXTRACTING: {DocumentStatus.ANALYZING, DocumentStatus.FAILED},
    DocumentStatus.ANALYZING: {DocumentStatus.COMPLETED, DocumentStatus.FAILED},
    DocumentStatus.FAILED: {DocumentStatus.QUEUED},
    DocumentStatus.COMPLETED: set(),
    DocumentStatus.DELETED: set(),
}


class InvalidDocumentTransition(ValueError):
    """The requested step would violate the document lifecycle."""


def transition_document(document: Document, target: DocumentStatus) -> None:
    if target not in TRANSITIONS[document.status]:
        raise InvalidDocumentTransition(f"{document.status} -> {target} is not allowed")
    document.status = target
