from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo


@dataclass(frozen=True)
class AlertCondition:
    metric: str
    direction: str
    threshold: float


def condition_matches(condition: AlertCondition, quote: dict) -> bool:
    quote_key = "current_price" if condition.metric == "price" else condition.metric
    actual = quote.get(quote_key, quote.get(condition.metric))
    if actual is None:
        return False
    value = float(actual)
    if condition.direction == "above":
        return value > float(condition.threshold)
    if condition.direction == "below":
        return value < float(condition.threshold)
    raise ValueError(f"unsupported direction: {condition.direction}")


def next_market_midnight(current: datetime, market_timezone: tzinfo) -> datetime:
    local = current.astimezone(market_timezone)
    tomorrow = local.date() + timedelta(days=1)
    return datetime.combine(tomorrow, time.min, market_timezone)

