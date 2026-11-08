from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.crazygame import __version__
from src.crazygame.api.dependencies import get_session
from src.crazygame.api.serializers import (
    group_dict,
    normalize_member_points,
    watchlist_dict,
)
from src.crazygame.domain.groups import (
    GroupSeriesMember,
    calculate_weighted_change,
    rebalanced_group_series,
    shared_group_scope,
)
from src.crazygame.domain.models import (
    AssetGroup,
    GroupMember,
    Instrument,
    WatchlistItem,
)
from src.crazygame.domain.schemas import GroupCreate, WatchlistCreate
from src.crazygame.services.catalog import search_instruments

router = APIRouter()
public_router = APIRouter()


def _fetch_member_points(quote_service, members, *, days: int) -> dict[int, list]:
    """并发获取组合成员的历史曲线，避免单个外部行情源拖慢整组请求。"""
    if not members:
        return {}
    max_workers = min(8, len(members))
    with ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="group-series",
    ) as executor:
        futures = {
            executor.submit(
                quote_service.fetch_daily_points,
                member.instrument,
                days=days,
            ): member.instrument_id
            for member in members
        }
        output: dict[int, list] = {}
        for future, instrument_id in futures.items():
            try:
                output[instrument_id] = future.result()
            except Exception:
                output[instrument_id] = []
        return output


def _upsert_instrument(db: Session, payload: WatchlistCreate) -> Instrument:
    """按 symbol、market、asset_type 获取或创建标准化标的。"""
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
    """返回容器健康检查所需的轻量状态响应。"""
    return {"status": "ok", "database": "ok"}


@public_router.get("/version")
def version():
    """返回后端当前版本号。"""
    return {"version": __version__}


@router.get("/instruments/search")
def instrument_search(
    q: str = Query(min_length=1),
    market: str = Query(default=""),
    asset_type: str = Query(default=""),
):
    """搜索并过滤可加入自选的股票、ETF 或场外基金。"""
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
    """返回单个标的的归一历史曲线，供自选项图表使用。"""
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
    """按股票/基金类型返回自选清单。"""
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
    """返回自选清单及其最新行情快照。"""
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
    """计算组合当日加权涨跌和行情覆盖率。"""
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
    """并发获取成员历史数据并生成组合归一曲线。"""
    group = db.get(AssetGroup, group_id)
    if group is None:
        raise HTTPException(404, "group not found")
    member_points = _fetch_member_points(
        request.app.state.quote_service,
        group.members,
        days=days,
    )
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
    """创建分类组合；服务端校验全部成员属于同一市场或基金类型。"""
    instrument_ids = [member.instrument_id for member in payload.members]
    instruments = db.scalars(
        select(Instrument).where(Instrument.id.in_(instrument_ids))
    ).all()
    found = {instrument.id for instrument in instruments}
    missing = set(instrument_ids) - found
    if missing:
        raise HTTPException(404, f"instruments not found: {sorted(missing)}")
    try:
        shared_group_scope(instruments)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
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
    """更新组合元数据和成员，并再次执行同一分类约束。"""
    group = db.get(AssetGroup, group_id)
    if group is None:
        raise HTTPException(404, "group not found")
    instrument_ids = [member.instrument_id for member in payload.members]
    instruments = db.scalars(
        select(Instrument).where(Instrument.id.in_(instrument_ids))
    ).all()
    found = {instrument.id for instrument in instruments}
    missing = set(instrument_ids) - found
    if missing:
        raise HTTPException(404, f"instruments not found: {sorted(missing)}")
    try:
        shared_group_scope(instruments)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
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

