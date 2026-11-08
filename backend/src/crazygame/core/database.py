from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.crazygame.core.config import AppConfig


class Base(DeclarativeBase):
    pass


def build_engine(config: AppConfig):
    url = config.resolved_database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)

    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


def build_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_scope(factory: sessionmaker) -> Iterator[Session]:
    session = factory()
    try:
        yield session
    finally:
        session.close()


def ensure_schema(engine) -> None:
    Base.metadata.create_all(bind=engine)
    if not engine.url.get_backend_name().startswith("sqlite"):
        return
    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.execute(
                text("PRAGMA table_info(notification_deliveries)")
            ).fetchall()
        }
        if columns and "context_json" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE notification_deliveries "
                    "ADD COLUMN context_json TEXT DEFAULT '{}'"
                )
            )

