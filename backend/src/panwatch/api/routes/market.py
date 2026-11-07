from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.panwatch import __version__
from src.panwatch.api.dependencies import get_session
from src.panwatch.api.serializers import (
    group_dict,
    normalize_member_points,
    watchlist_dict,
)
from src.panwatch.domain.groups import (
    GroupSeriesMember,
    calculate_weighted_change,
    rebalanced_group_series,
)
from src.panwatch.domain.models import (
    AssetGroup,
    GroupMember,
    Instrument,
    WatchlistItem,
)
from src.panwatch.domain.schemas import GroupCreate, WatchlistCreate
from src.panwatch.services.catalog import search_instruments

router = APIRouter()
public_router = APIRouter()


def _upsert_instrument(db: Session, payload: WatchlistCreate) -> Instrument:
    instrument = db.scalar(
        select(Instrument).where(
            Instrument.symbol == payload.symbol,
            Instrument.market == payload.market,
            Instrument.asset_type == payload.asset_type,
        )
    )
    if instrument:
        return instrument
    currency = "HKD" if payload.market == "HK" else "USD" if payload.market == "US" else "CNY"
    quote_mode = "estimated" if payload.asset_type == "open_end_fund" else "realtime"
    instrument = Instrument(
        symbol=payload.symbol,
        name=payload.name,
        market=payload.market,
        asset_type=payload.asset_type,
        currency=currency,
        quote_mode=quote_mode,
    )
    db.add(instrument)
    db.flush()
    return instrument


@public_router.get("/health")
def health():
    return {"status": "ok", "database": "ok"}


@public_router.get("/version")
def version():
    return {"version": __version__}


@router.get("/instruments/search")
def instrument_search(
    q: str = Query(min_length=1),
    market: str = Query(default=""),
    asset_type: str = Query(default=""),
):
    items = search_instruments(q, market=market, asset_type=asset_type)
    return {
        "items": [
            {
                "symbol": item.symbol,
                "name": item.name,
                "market": item.market,
                "asset_type": item.asset_type,
                "currency": item.currency,
                "quote_mode": item.quote_mode,
            }
            for item in items
        ]
    }


@router.get("/instruments/{instrument_id}/series")
def instrument_series(
    instrument_id: int,
    request: Request,
    days: int = Query(default=365, ge=7, le=3650),
    db: Session = Depends(get_session),
):
    instrument = db.get(Instrument, instrument_id)
    if instrument is None:
        raise HTTPException(404, "instrument not found")
    points = request.app.state.quote_service.fetch_daily_points(
        instrument,
        days=days,
    )
    return {
        "instrument_id": instrument.id,
        "symbol": instrument.symbol,
        "name": instrument.name,
        "points": normalize_member_points(points),
    }


@router.get("/watchlist")
def list_watchlist(
    kind: str = Query(default=""),
    db: Session = Depends(get_session),
):
    query = select(WatchlistItem).order_by(
        WatchlistItem.sort_order.asc(), WatchlistItem.id.asc()
    )
    if kind:
        query = query.where(WatchlistItem.kind == kind)
    items = db.scalars(query).all()
    return {"items": [watchlist_dict(item) for item in items]}


@router.get("/quotes")
def watchlist_quotes(
    request: Request,
    kind: str = Query(default=""),
    db: Session = Depends(get_session),
):
    query = select(WatchlistItem).order_by(
        WatchlistItem.sort_order.asc(), WatchlistItem.id.asc()
    )
    if kind:
        query = query.where(WatchlistItem.kind == kind)
    items = db.scalars(query).all()
    quotes = request.app.state.quote_service.fetch_quotes(
        [item.instrument for item in items]
    )
    return {
        "items": [
            {
                **watchlist_dict(item),
                "quote": (
                    quotes.get((item.instrument.symbol, item.instrument.market)).as_dict()
                    if quotes.get((item.instrument.symbol, item.instrument.market))
                    else None
                ),
            }
            for item in items
        ]
    }


@router.post("/watchlist", status_code=201)
def add_watchlist(payload: WatchlistCreate, db: Session = Depends(get_session)):
    instrument = _upsert_instrument(db, payload)
    item = db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.instrument_id == instrument.id,
            WatchlistItem.kind == payload.kind,
        )
    )
    if item is None:
        current = db.scalars(select(WatchlistItem)).all()
        item = WatchlistItem(
            instrument_id=instrument.id,
            kind=payload.kind,
            sort_order=len(current),
        )
        db.add(item)
    db.commit()
    db.refresh(item)
    return watchlist_dict(item)


@router.delete("/watchlist/{item_id}")
def delete_watchlist(item_id: int, db: Session = Depends(get_session)):
    item = db.get(WatchlistItem, item_id)
    if item is None:
        raise HTTPException(404, "watchlist item not found")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/groups")
def list_groups(db: Session = Depends(get_session)):
    groups = db.scalars(select(AssetGroup).order_by(AssetGroup.sort_order)).all()
    return {"items": [group_dict(group) for group in groups]}


@router.get("/groups/{group_id}/summary")
def group_summary(group_id: int, request: Request, db: Session = Depends(get_session)):
    group = db.get(AssetGroup, group_id)
    if group is None:
        raise HTTPException(404, "group not found")
    quotes = request.app.state.quote_service.fetch_quotes(
        [member.instrument for member in group.members]
    )
    change, coverage = calculate_weighted_change(
        [
            (
                member.weight,
                (
                    quotes.get((member.instrument.symbol, member.instrument.market)).change_pct
                    if quotes.get((member.instrument.symbol, member.instrument.market))
                    else None
                ),
            )
            for member in group.members
        ]
    )
    return {
        **group_dict(group),
        "day_change_pct": change,
        "coverage": coverage,
    }


@router.get("/groups/{group_id}/series")
def group_series(
    group_id: int,
    request: Request,
    days: int = Query(default=365, ge=7, le=3650),
    db: Session = Depends(get_session),
):
    group = db.get(AssetGroup, group_id)
    if group is None:
        raise HTTPException(404, "group not found")
    member_points = {
        member.instrument_id: request.app.state.quote_service.fetch_daily_points(
            member.instrument, days=days
        )
        for member in group.members
    }
    members = [
        GroupSeriesMember(
            instrument_id=member.instrument_id,
            weight=member.weight,
            points=member_points[member.instrument_id],
        )
        for member in group.members
    ]
    points = rebalanced_group_series(members)
    return {
        "group_id": group.id,
        "range_days": days,
        "points": [
            {
                "date": point.date.isoformat(),
                "value": round(point.value, 4),
                "coverage": round(point.coverage, 4),
            }
            for point in points
        ],
        "members": [
            {
                "instrument_id": member.instrument_id,
                "name": member.instrument.name,
                "symbol": member.instrument.symbol,
                "points": normalize_member_points(
                    member_points[member.instrument_id]
                ),
            }
            for member in group.members
        ],
    }


@router.post("/groups", status_code=201)
def create_group(payload: GroupCreate, db: Session = Depends(get_session)):
    instrument_ids = [member.instrument_id for member in payload.members]
    found = set(db.scalars(select(Instrument.id).where(Instrument.id.in_(instrument_ids))).all())
    missing = set(instrument_ids) - found
    if missing:
        raise HTTPException(404, f"instruments not found: {sorted(missing)}")
    group = AssetGroup(name=payload.name, description=payload.description)
    group.members = [
        GroupMember(instrument_id=member.instrument_id, weight=member.weight)
        for member in payload.members
    ]
    db.add(group)
    db.commit()
    db.refresh(group)
    return group_dict(group)


@router.put("/groups/{group_id}")
def update_group(group_id: int, payload: GroupCreate, db: Session = Depends(get_session)):
    group = db.get(AssetGroup, group_id)
    if group is None:
        raise HTTPException(404, "group not found")
    group.name = payload.name
    group.description = payload.description
    group.members = [
        GroupMember(instrument_id=member.instrument_id, weight=member.weight)
        for member in payload.members
    ]
    db.commit()
    db.refresh(group)
    return group_dict(group)


@router.delete("/groups/{group_id}")
def delete_group(group_id: int, db: Session = Depends(get_session)):
    group = db.get(AssetGroup, group_id)
    if group is None:
        raise HTTPException(404, "group not found")
    db.delete(group)
    db.commit()
    return {"ok": True}

