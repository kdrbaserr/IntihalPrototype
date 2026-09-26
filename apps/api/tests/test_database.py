from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from intihal_api.db.base import BaseModel
from intihal_api.db.session import AsyncSessionFactory, engine


class ExampleModel(BaseModel):
    __tablename__ = "example_models"


def test_database_uses_async_driver_and_sessions() -> None:
    assert engine.dialect.is_async is True
    assert engine.url.drivername == "postgresql+asyncpg"
    assert AsyncSessionFactory.class_ is AsyncSession
    assert AsyncSessionFactory.kw["expire_on_commit"] is False


def test_shared_model_fields_are_defined_once() -> None:
    mapper = inspect(ExampleModel)

    assert set(mapper.columns.keys()) == {"id", "created_at", "updated_at"}
    assert mapper.columns.id.primary_key is True
    assert mapper.columns.id.default.is_callable is True
    assert mapper.columns.created_at.nullable is False
    assert mapper.columns.created_at.server_default is not None
    assert mapper.columns.updated_at.nullable is False
    assert mapper.columns.updated_at.server_default is not None
    assert mapper.columns.updated_at.onupdate is not None
