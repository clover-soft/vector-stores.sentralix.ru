from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import get_config

Base = declarative_base()

_engine = None
_session_maker: sessionmaker | None = None


def get_engine():
    global _engine

    if _engine is not None:
        return _engine

    config = get_config()
    if not config.database_uri:
        raise RuntimeError("DATABASE_URI не задан")

    _engine = create_engine(
        config.database_uri,
        pool_pre_ping=True,
    )
    return _engine


def get_session_maker() -> sessionmaker:
    global _session_maker

    if _session_maker is not None:
        return _session_maker

    _session_maker = sessionmaker(
        bind=get_engine(),
        autocommit=False,
        autoflush=False,
    )
    return _session_maker


def get_db() -> Generator[Session, None, None]:
    session_local = get_session_maker()
    db: Session = session_local()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    config = get_config()
    if not config.database_uri:
        return

    import models.rag_file

    _ = models.rag_file.RagFile

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
