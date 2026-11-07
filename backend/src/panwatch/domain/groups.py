from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite


@dataclass(frozen=True)
class GroupSeriesMember:
    instrument_id: int
    weight: float
    points: list[tuple[date, float]]


@dataclass(frozen=True)
class GroupSeriesPoint:
    date: date
    value: float
    coverage: float


def normalize_weights(weights: list[float]) -> list[float]:
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

