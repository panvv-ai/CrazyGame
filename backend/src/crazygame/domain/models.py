from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.crazygame.core.database import Base


def utc_now() -> datetime:
    """返回不带 tzinfo 的 UTC 当前时间，统一数据库时间存储口径。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Instrument(Base):
    """标准化投资标的。

    股票、场内 ETF 和场外基金共用一张表，通过 market 与 asset_type 区分交易市场、
    资产类型和行情模式；symbol、market、asset_type 三者共同保证唯一性。
    """
    __tablename__ = "instruments"
    __table_args__ = (
        UniqueConstraint("symbol", "market", "asset_type", name="uq_instrument_identity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    market: Mapped[str] = mapped_column(String(16), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    quote_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class WatchlistItem(Base):
    """自选清单中的一条记录，kind 用于区分股票自选和基金自选。"""
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint("instrument_id", "kind", name="uq_watchlist_instrument_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    instrument: Mapped[Instrument] = relationship(lazy="joined")


class AssetGroup(Base):
    """用户创建的加权组合；成员权重保存在 GroupMember 中。"""
    __tablename__ = "asset_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    members: Mapped[list[GroupMember]] = relationship(
        back_populates="group", cascade="all, delete-orphan", lazy="selectin"
    )


class GroupMember(Base):
    """组合成员关系，记录标的及用户输入的相对权重。"""
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "instrument_id", name="uq_group_instrument"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("asset_groups.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    group: Mapped[AssetGroup] = relationship(back_populates="members")
    instrument: Mapped[Instrument] = relationship(lazy="joined")


class Holding(Base):
    """单账户轻量持仓，只保存数量、平均成本与备注。"""
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("instrument_id", name="uq_holding_instrument"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    average_cost: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str] = mapped_column(String(500), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    instrument: Mapped[Instrument] = relationship(lazy="joined")


class NotifyChannel(Base):
    """飞书或短信通知渠道，敏感配置以加密文本保存。"""
    __tablename__ = "notify_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    config_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AlertRule(Base):
    """价格或涨跌幅提醒规则，包含方向、阈值、冷却和交易时段约束。"""
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), default="")
    metric: Mapped[str] = mapped_column(String(24), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    channel_ids: Mapped[str] = mapped_column(Text, default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    once_per_day: Mapped[bool] = mapped_column(Boolean, default=True)
    market_hours_only: Mapped[bool] = mapped_column(Boolean, default=True)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    instrument: Mapped[Instrument] = relationship(lazy="joined")


class AlertHit(Base):
    """一次提醒命中快照，保留触发值和当时行情，便于审计与展示。"""
    __tablename__ = "alert_hits"
    __table_args__ = (Index("ix_alert_hits_rule_time", "rule_id", "triggered_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("alert_rules.id", ondelete="CASCADE"), nullable=False
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    rule: Mapped[AlertRule] = relationship(lazy="joined")
    instrument: Mapped[Instrument] = relationship(lazy="joined")


class NotificationDelivery(Base):
    """提醒消息的投递任务与重试状态。"""
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        Index("ix_delivery_status_next", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hit_id: Mapped[int] = mapped_column(
        ForeignKey("alert_hits.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("notify_channels.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(24), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=6)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, default=utc_now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_code: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class DailyReview(Base):
    """按交易日生成的 AI 持仓健康简报，成功结果按日期唯一。"""
    __tablename__ = "daily_reviews"
    __table_args__ = (UniqueConstraint("trade_date", name="uq_daily_review_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[str] = mapped_column(String(10), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    snapshot_json: Mapped[str] = mapped_column(Text, default="{}")
    model_label: Mapped[str] = mapped_column(String(120), default="")
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class AIReport(Base):
    """按需生成的单标的 AI 决策报告。"""
    __tablename__ = "ai_reports"
    __table_args__ = (
        Index("ix_ai_reports_instrument_created", "instrument_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), default="pending")
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), default="neutral")
    confidence: Mapped[str] = mapped_column(String(16), default="medium")
    score: Mapped[int] = mapped_column(Integer, default=50)
    title: Mapped[str] = mapped_column(String(255), default="")
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    report_json: Mapped[str] = mapped_column(Text, default="{}")
    context_json: Mapped[str] = mapped_column(Text, default="{}")
    model_label: Mapped[str] = mapped_column(String(120), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    instrument: Mapped[Instrument] = relationship(lazy="joined")


class AIChatSession(Base):
    """单操作者的 AI 问股会话，每个会话只维护一个主讨论标的。"""
    __tablename__ = "ai_chat_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    active_instrument_id: Mapped[int | None] = mapped_column(
        ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(160), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    active_instrument: Mapped[Instrument | None] = relationship(lazy="joined")
    messages: Mapped[list[AIChatMessage]] = relationship(
        back_populates="session", cascade="all, delete-orphan", lazy="selectin"
    )


class AIChatMessage(Base):
    """问股会话中持久化的用户可见消息和工具摘要。"""
    __tablename__ = "ai_chat_messages"
    __table_args__ = (
        Index("ix_ai_chat_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    session: Mapped[AIChatSession] = relationship(back_populates="messages")


class MarketIntel(Base):
    """新闻、公告和热点证据缓存，支持离线降级与来源追溯。"""
    __tablename__ = "market_intels"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "dedupe_key",
            name="uq_market_intel_instrument_key",
        ),
        Index("ix_market_intels_instrument_fetched", "instrument_id", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int | None] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE"), nullable=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="")
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    relevance_kind: Mapped[str] = mapped_column(String(16), default="macro")
    relevance_score: Mapped[int] = mapped_column(Integer, default=0)
    raw_json: Mapped[str] = mapped_column(Text, default="{}")


class AppSetting(Base):
    """通用键值配置表，保存语言、AI 和简报等应用设置。"""
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

