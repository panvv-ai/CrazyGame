from __future__ import annotations

from src.crazygame.domain.groups import normalize_weights, shared_group_scope
from src.crazygame.domain.models import AssetGroup, Instrument, WatchlistItem


def instrument_dict(instrument: Instrument) -> dict:
    """序列化标准化标的，字段与前端 Instrument 类型保持一致。"""
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
    """序列化自选项，并把标的身份字段展开到同一层级。"""
    return {
        "id": item.id,
        "instrument_id": item.instrument_id,
        "kind": item.kind,
        "sort_order": item.sort_order,
        **instrument_dict(item.instrument),
    }


def group_dict(group: AssetGroup) -> dict:
    """序列化组合、分类和归一后成员权重。"""
    weights = normalize_weights([member.weight for member in group.members])
    try:
        scope = shared_group_scope([member.instrument for member in group.members])
    except ValueError:
        scope = "mixed"
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "scope": scope,
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
    """把原始价格点转换为以首个有效值为 100 的归一序列。"""
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

