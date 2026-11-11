from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from functools import wraps
from threading import RLock

from sqlalchemy import select

from src.crazygame.domain.alerts import AlertCondition, condition_matches
from src.crazygame.domain.models import (
    AlertHit,
    AlertRule,
    NotificationDelivery,
    NotifyChannel,
    utc_now,
)
from src.crazygame.services.market import MARKET_TIMEZONES, is_market_open
from src.crazygame.services.notifications import render_alert_message
from src.crazygame.services.senders import NotificationSender

_ALERT_SCAN_LOCK = RLock()


def _serialized_scan(method):
    """串行化单进程内的提醒判定，避免立即检查与定时扫描重复命中。"""
    @wraps(method)
    def wrapper(*args, **kwargs):
        with _ALERT_SCAN_LOCK:
            return method(*args, **kwargs)

    return wrapper


def _as_utc_naive(value: datetime) -> datetime:
    """把带时区时间转换为数据库使用的 naive UTC。"""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class AlertScanner:
    """提醒扫描器：读取启用规则、获取行情、判断条件并生成待投递消息。"""

    def __init__(self, session_factory, quote_service, secret_box):
        self.session_factory = session_factory
        self.quote_service = quote_service
        self.secret_box = secret_box

    @_serialized_scan
    def scan_once(self, *, now: datetime | None = None) -> dict:
        """执行一次完整提醒扫描并返回触发与跳过数量。

        now 可注入固定时间，便于测试交易时段、每日一次和冷却窗口逻辑。
        """
        current = now or datetime.now(timezone.utc)
        with self.session_factory() as db:
            rules = db.scalars(
                select(AlertRule).where(AlertRule.enabled.is_(True))
            ).all()
            instruments = {rule.instrument_id: rule.instrument for rule in rules}
            quotes = self.quote_service.fetch_quotes(list(instruments.values()))
            triggered = 0
            skipped = 0
            for rule in rules:
                quote = quotes.get((rule.instrument.symbol, rule.instrument.market))
                if self._process_rule(db, rule, quote, current) == "triggered":
                    triggered += 1
                else:
                    skipped += 1
            db.commit()
            return {"triggered": triggered, "skipped": skipped}

    @_serialized_scan
    def scan_rule(self, rule_id: int, *, now: datetime | None = None) -> dict:
        """立即检查单条规则并处理投递记录，不影响其他规则的调度周期。"""
        current = now or datetime.now(timezone.utc)
        with self.session_factory() as db:
            rule = db.get(AlertRule, rule_id)
            if rule is None:
                return {"triggered": 0, "skipped": 1, "reason": "not_found"}
            if not rule.enabled:
                return {"triggered": 0, "skipped": 1, "reason": "disabled"}
            quotes = self.quote_service.fetch_quotes([rule.instrument])
            quote = quotes.get((rule.instrument.symbol, rule.instrument.market))
            result = self._process_rule(db, rule, quote, current)
            db.commit()
            return {
                "triggered": 1 if result == "triggered" else 0,
                "skipped": 0 if result == "triggered" else 1,
                "reason": result,
            }

    def _process_rule(self, db, rule: AlertRule, quote, current: datetime) -> str:
        """判断并执行单条规则，返回可用于界面反馈的稳定原因码。"""
        market = rule.instrument.market
        if rule.market_hours_only and not is_market_open(market, current):
            return "market_closed"
        if quote is None:
            return "quote_unavailable"
        market_now = current.astimezone(MARKET_TIMEZONES[market])
        if rule.once_per_day and rule.last_triggered_at:
            last_local = (
                rule.last_triggered_at.replace(tzinfo=timezone.utc)
                .astimezone(MARKET_TIMEZONES[market])
            )
            if last_local.date() == market_now.date():
                return "daily_limited"
        if not rule.once_per_day and rule.last_triggered_at:
            last = rule.last_triggered_at.replace(tzinfo=timezone.utc)
            if current - last < timedelta(minutes=rule.cooldown_minutes):
                return "cooling_down"

        quote_dict = quote.as_dict()
        condition = AlertCondition(
            metric=rule.metric,
            direction=rule.direction,
            threshold=rule.threshold,
        )
        if not condition_matches(condition, quote_dict):
            return "condition_not_met"

        observed_key = "current_price" if rule.metric == "price" else rule.metric
        observed = float(quote_dict[observed_key])
        hit = AlertHit(
            rule_id=rule.id,
            instrument_id=rule.instrument_id,
            triggered_at=_as_utc_naive(current),
            observed_value=observed,
            snapshot_json=json.dumps(quote_dict, ensure_ascii=False),
        )
        db.add(hit)
        db.flush()
        channel_ids = json.loads(rule.channel_ids or "[]")
        channels = db.scalars(
            select(NotifyChannel).where(
                NotifyChannel.id.in_(channel_ids),
                NotifyChannel.enabled.is_(True),
            )
        ).all()
        language = self._language(db)
        for channel in channels:
            message = render_alert_message(
                rule.name or "Alert",
                quote_dict,
                language,
            )
            db.add(
                NotificationDelivery(
                    hit_id=hit.id,
                    channel_id=channel.id,
                    title=message["title"],
                    content=message["body"],
                    context_json=json.dumps(
                        {
                            "rule": rule.name,
                            "name": quote_dict.get("name"),
                            "symbol": quote_dict.get("symbol"),
                            "current_price": quote_dict.get("current_price"),
                            "change_pct": quote_dict.get("change_pct"),
                            "language": language,
                        },
                        ensure_ascii=False,
                    ),
                )
            )
        rule.last_triggered_at = _as_utc_naive(current)
        return "triggered"

    @staticmethod
    def _language(db) -> str:
        """读取当前界面语言，供提醒标题和正文做双语渲染。"""
        from src.crazygame.domain.models import AppSetting

        setting = db.get(AppSetting, "language")
        return setting.value if setting else "zh-CN"


class DeliveryWorker:
    """通知投递工作器：发送待处理消息，并维护指数退避重试状态。"""

    def __init__(self, session_factory, secret_box, sender=None):
        self.session_factory = session_factory
        self.secret_box = secret_box
        self.sender = sender or NotificationSender()

    def drain(self, limit: int = 20) -> dict:
        """处理一批 pending/retry 消息，单条失败不会阻断后续投递。"""
        processed = 0
        with self.session_factory() as db:
            deliveries = db.scalars(
                select(NotificationDelivery)
                .where(
                    NotificationDelivery.status.in_(("pending", "retry")),
                    NotificationDelivery.next_attempt_at <= utc_now(),
                    NotificationDelivery.attempts < NotificationDelivery.max_attempts,
                )
                .order_by(NotificationDelivery.id)
                .limit(limit)
            ).all()
            for delivery in deliveries:
                channel = db.get(NotifyChannel, delivery.channel_id)
                if channel is None or not channel.enabled:
                    delivery.status = "blocked"
                    delivery.error_code = "channel_unavailable"
                    continue
                delivery.status = "sending"
                delivery.attempts += 1
                db.commit()
                try:
                    config = json.loads(self.secret_box.decrypt(channel.config_encrypted))
                    ok = self.sender.send(
                        channel.type,
                        config,
                        delivery.title,
                        delivery.content,
                        context=json.loads(delivery.context_json or "{}"),
                    )
                except Exception:
                    ok = False
                if ok:
                    delivery.status = "delivered"
                    delivery.delivered_at = utc_now()
                    delivery.error_code = ""
                    delivery.next_attempt_at = None
                else:
                    delivery.error_code = "send_failed"
                    if delivery.attempts >= delivery.max_attempts:
                        delivery.status = "failed"
                        delivery.next_attempt_at = None
                    else:
                        delivery.status = "retry"
                        delivery.next_attempt_at = utc_now() + timedelta(
                            seconds=min(900, 30 * 2 ** (delivery.attempts - 1))
                        )
                db.commit()
                processed += 1
        return {"processed": processed}

