from __future__ import annotations

from collections.abc import Generator
import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import get_config

logger = logging.getLogger("vector-stores.database")

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

    try:
        safe_uri = make_url(config.database_uri).render_as_string(hide_password=True)
    except Exception:
        safe_uri = "<invalid DATABASE_URI>"

    logger.info("Подключение к базе данных: %s", safe_uri)

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
    import models.rag_index
    import models.rag_index_file

    _ = models.rag_file.RagFile
    _ = models.rag_index.RagIndex
    _ = models.rag_index_file.RagIndexFile

    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        logger.info("Подключение к базе данных успешно")
    except Exception:
        logger.exception("Ошибка подключения к базе данных")
        raise

    Base.metadata.create_all(bind=engine)
