from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Iterable, Protocol


class ScopedInstrument(Protocol):
    """组合校验所需的最小标的接口，避免领域逻辑依赖 ORM 实现。"""

    market: str
    asset_type: str


def instrument_scope(market: str, asset_type: str) -> str:
    """把标的转换为组合分类。

    股票按 A 股、港股、美股拆分；基金按场内 ETF、场外基金拆分。组合只能在
    同一个分类内构建。
    """
    if asset_type == "listed_etf":
        return "fund_listed"
    if asset_type == "open_end_fund":
        return "fund_open_end"
    if asset_type == "stock" and market in {"CN", "HK", "US"}:
        return f"stock_{market.lower()}"
    raise ValueError("unsupported instrument scope")


def shared_group_scope(instruments: Iterable[ScopedInstrument]) -> str:
    """校验成员属于同一分类并返回该分类；混合组合会抛出 ValueError。"""
    scopes = {instrument_scope(item.market, item.asset_type) for item in instruments}
    if len(scopes) != 1:
        raise ValueError("group members must share one scope")
    return scopes.pop()


@dataclass(frozen=True)
class GroupSeriesMember:
    """组合曲线计算所需的单个成员历史数据。"""

    instrument_id: int
    weight: float
    points: list[tuple[date, float]]


@dataclass(frozen=True)
class GroupSeriesPoint:
    """组合归一曲线的单日结果，coverage 表示当日有效权重覆盖率。"""

    date: date
    value: float
    coverage: float


def normalize_weights(weights: list[float]) -> list[float]:
    """把相对权重归一为总和 1，并拒绝负数、非有限值和全零权重。"""
    if not weights:
        return []
    values = [float(weight) for weight in weights]
    if any(not isfinite(weight) or weight < 0 for weight in values):
        raise ValueError("weights must be finite and non-negative")
    total = sum(values)
    if total <= 0:
        raise ValueError("weights must have a positive total")
    return [weight / total for weight in values]


def calculate_weighted_change(
    members: list[tuple[float, float | None]],
) -> tuple[float | None, float]:
    """计算组合当日加权涨跌。

    缺失行情的成员会被暂时剔除，并按剩余有效权重重新归一；第二个返回值是有效
    权重占全部目标权重的比例。
    """
    total_weight = sum(float(weight) for weight, _ in members)
    if total_weight <= 0:
        return None, 0.0

    available = [
        (float(weight), float(change))
        for weight, change in members
        if change is not None
    ]
    available_weight = sum(weight for weight, _ in available)
    if available_weight <= 0:
        return None, 0.0

    value = sum(weight * change for weight, change in available) / available_weight
    return value, available_weight / total_weight


def rebalanced_group_series(members: list[GroupSeriesMember]) -> list[GroupSeriesPoint]:
    """根据目标权重和历史价格生成组合归一曲线。

    曲线从 100 开始，逐日应用有效成员的加权收益率；缺失数据的成员只降低覆盖率，
    不会把整条组合曲线打断。
    """
    if not members:
        return []

    normalized = normalize_weights([member.weight for member in members])
    histories = [
        {point_date: float(value) for point_date, value in member.points}
        for member in members
    ]
    all_dates = sorted({point_date for history in histories for point_date in history})
    if not all_dates:
        return []

    previous = [history.get(all_dates[0]) for history in histories]
    curve = 100.0
    output: list[GroupSeriesPoint] = []
    initial_weight = sum(
        weight for weight, value in zip(normalized, previous) if value is not None
    )
    output.append(
        GroupSeriesPoint(
            date=all_dates[0],
            value=curve,
            coverage=initial_weight,
        )
    )

    for point_date in all_dates[1:]:
        current = [history.get(point_date) for history in histories]
        available: list[tuple[float, float]] = []
        for weight, before, after in zip(normalized, previous, current):
            if before is None or after is None or before <= 0:
                continue
            available.append((weight, after / before - 1.0))

        available_weight = sum(weight for weight, _ in available)
        if available_weight > 0:
            day_return = (
                sum(weight * change for weight, change in available) / available_weight
            )
            curve *= 1.0 + day_return

        output.append(
            GroupSeriesPoint(
                date=point_date,
                value=curve,
                coverage=available_weight,
            )
        )
        previous = [
            after if after is not None else before
            for before, after in zip(previous, current)
        ]

    return output

