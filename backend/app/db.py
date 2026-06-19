"""SQLAlchemy engine/session. DB is optional — import never crashes the app."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


_engine = None
_Session = None


def engine():
    global _engine, _Session
    if _engine is None:
        _engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        _Session = sessionmaker(bind=_engine, autoflush=False, future=True)
    return _engine


def get_session() -> Iterator[Session]:
    engine()
    db = _Session()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from . import models  # noqa: F401  (register tables)
    Base.metadata.create_all(bind=engine())
