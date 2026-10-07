"""Typed allowlist for audit events; callers commit with the business change."""

from enum import StrEnum
from typing import Protocol
from uuid import UUID

from intihal_api.db.models import AuditEvent


class AuditAction(StrEnum):
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_DELETE = "document.delete"
    SOURCE_CREATE = "admin.source.create"
    SOURCE_LIST = "admin.source.list"
    SOURCE_DISABLE = "admin.source.disable"
    SOURCE_REINDEX = "admin.source.reindex"
    USER_PROVISION = "admin.user.provision"


class AuditActor(StrEnum):
    USER = "user"
    SYSTEM = "system"
    OPERATOR = "operator"


class AuditOutcome(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AuditSession(Protocol):
    def add_all(self, instances: list[object]) -> None: ...


def record_audit(
    session: AuditSession,
    *,
    action: AuditAction,
    actor_id: UUID | None = None,
    actor_kind: AuditActor = AuditActor.USER,
    resource_id: UUID | None = None,
    outcome: AuditOutcome = AuditOutcome.SUCCEEDED,
) -> None:
    # Do not accept arbitrary strings or request dictionaries, even from internal callers.
    if (
        not isinstance(action, AuditAction)
        or not isinstance(actor_kind, AuditActor)
        or not isinstance(outcome, AuditOutcome)
    ):
        raise ValueError("Audit fields must use the fixed allowlist")
    if (actor_kind is AuditActor.USER) != (actor_id is not None):
        raise ValueError("Only authenticated user actors carry a user ID")
    if actor_id is not None and not isinstance(actor_id, UUID):
        raise ValueError("Audit actor ID must be a UUID")
    if resource_id is not None and not isinstance(resource_id, UUID):
        raise ValueError("Audit resource ID must be a UUID")
    if resource_id is None and action is not AuditAction.SOURCE_LIST:
        raise ValueError("This audit operation requires a resource ID")
    resource_type = (
        "document"
        if action.value.startswith("document.")
        else "user"
        if action is AuditAction.USER_PROVISION
        else "source"
    )
    session.add_all(
        [
            AuditEvent(
                actor_id=actor_id,
                actor_kind=actor_kind.value,
                action=action.value,
                resource_type=resource_type,
                resource_id=resource_id,
                outcome=outcome.value,
            )
        ]
    )
