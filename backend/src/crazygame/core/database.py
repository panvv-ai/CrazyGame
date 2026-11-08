from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.crazygame.core.config import AppConfig


class Base(DeclarativeBase):
    """所有 SQLAlchemy ORM 模型的声明式基类。"""


def build_engine(config: AppConfig):
    """根据配置创建数据库引擎，并为 SQLite 启用适合本地服务并发访问的参数。

    WAL 允许读写并发，foreign_keys 保证级联删除有效，busy_timeout 避免短暂写锁
    直接导致请求失败。
    """
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
    """创建会话工厂；提交后保留对象属性，便于路由层直接序列化 ORM 对象。"""
    return sessionmaker(bind=engine, expire_on_commit=False)


def session_scope(factory: sessionmaker) -> Iterator[Session]:
    """提供上下文式数据库会话，确保异常或提前退出时连接一定关闭。"""
    session = factory()
    try:
        yield session
    finally:
        session.close()


def ensure_schema(engine) -> None:
    """创建缺失的数据表，并执行项目当前需要的轻量 SQLite 兼容迁移。"""
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

