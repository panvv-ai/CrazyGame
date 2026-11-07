from __future__ import annotations

from src.panwatch.domain.groups import normalize_weights
from src.panwatch.domain.models import AssetGroup, Instrument, WatchlistItem


def instrument_dict(instrument: Instrument) -> dict:
    return {
        "id": instrument.id,
        "symbol": instrument.symbol,
        "name": instrument.name,
        "market": instrument.market,
        "asset_type": instrument.asset_type,
        "currency": instrument.currency,
        "quote_mode": instrument.quote_mode,
    }


def watchlist_dict(item: WatchlistItem) -> dict:
    return {
        "id": item.id,
        "instrument_id": item.instrument_id,
        "kind": item.kind,
        "sort_order": item.sort_order,
        **instrument_dict(item.instrument),
    }


def group_dict(group: AssetGroup) -> dict:
    weights = normalize_weights([member.weight for member in group.members])
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "members": [
            {
                "instrument_id": member.instrument_id,
                "weight": member.weight,
                "normalized_weight": normalized,
                **instrument_dict(member.instrument),
            }
            for member, normalized in zip(group.members, weights)
        ],
    }


def normalize_member_points(points) -> list[dict]:
    first = next((value for _, value in points if value > 0), None)
    if first is None:
        return []
    return [
        {
            "date": point_date.isoformat(),
            "value": round(value / first * 100.0, 4),
        }
        for point_date, value in points
    ]

