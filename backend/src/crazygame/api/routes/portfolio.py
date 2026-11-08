from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.crazygame.api.dependencies import get_session
from src.crazygame.api.serializers import instrument_dict
from src.crazygame.domain.groups import GroupSeriesMember, rebalanced_group_series
from src.crazygame.domain.models import Holding, Instrument

router = APIRouter()


class HoldingPayload(BaseModel):
    instrument_id: int
    quantity: float = Field(ge=0)
    average_cost: float = Field(ge=0)
    note: str = ""


@router.get("")
def list_holdings(request: Request, db=Depends(get_session)):
    rows = db.scalars(select(Holding).order_by(Holding.id)).all()
    quote_service = request.app.state.quote_service
    quotes = quote_service.fetch_quotes([row.instrument for row in rows])
    items = []
    for row in rows:
        quote = quotes.get((row.instrument.symbol, row.instrument.market))
        current_price = quote.current_price if quote else None
        market_value = (
            current_price * row.quantity if current_price is not None else None
        )
        cost = row.average_cost * row.quantity
        pnl = market_value - cost if market_value is not None else None
        items.append(
            {
                "id": row.id,
                "quantity": row.quantity,
                "average_cost": row.average_cost,
                "note": row.note,
                "instrument_id": row.instrument_id,
                **instrument_dict(row.instrument),
                "quote": quote.as_dict() if quote else None,
                "current_price": current_price,
                "market_value": market_value,
                "unrealized_pnl": pnl,
            }
        )
    return {"items": items}


@router.get("/series")
def holding_series(
    request: Request,
    days: int = Query(default=365, ge=7, le=3650),
    db=Depends(get_session),
):
    """按币种生成真实持仓的加权归一曲线。

    权重使用当前市值；行情暂时不可用时回退到成本市值，避免整只持仓从图中消失。
    不同币种不做隐含汇率换算，因此分别返回独立曲线。
    """
    holdings = db.scalars(select(Holding).order_by(Holding.id)).all()
    if not holdings:
        return {"series": []}
    quote_service = request.app.state.quote_service
    quotes = quote_service.fetch_quotes([row.instrument for row in holdings])

    def fetch_history(holding: Holding):
        try:
            return holding.instrument_id, quote_service.fetch_daily_points(
                holding.instrument,
                days=days,
            )
        except Exception:
            return holding.instrument_id, []

    with ThreadPoolExecutor(
        max_workers=min(8, len(holdings)),
        thread_name_prefix="holding-series",
    ) as executor:
        histories = dict(executor.map(fetch_history, holdings))

    grouped: dict[str, list[GroupSeriesMember]] = {}
    for holding in holdings:
        quote = quotes.get((holding.instrument.symbol, holding.instrument.market))
        current_value = (
            quote.current_price * holding.quantity
            if quote and quote.current_price is not None
            else holding.average_cost * holding.quantity
        )
        if current_value <= 0:
            continue
        grouped.setdefault(holding.instrument.currency, []).append(
            GroupSeriesMember(
                instrument_id=holding.instrument_id,
                weight=current_value,
                points=histories.get(holding.instrument_id, []),
            )
        )

    output = []
    for currency, members in sorted(grouped.items()):
        points = rebalanced_group_series(members)
        output.append(
            {
                "currency": currency,
                "points": [
                    {
                        "date": point.date.isoformat(),
                        "value": round(point.value, 4),
                        "coverage": round(point.coverage, 4),
                    }
                    for point in points
                ],
            }
        )
    return {"series": output}


@router.put("")
def upsert_holding(payload: HoldingPayload, db=Depends(get_session)):
    instrument = db.get(Instrument, payload.instrument_id)
    if instrument is None:
        raise HTTPException(404, "instrument not found")
    row = db.scalar(
        select(Holding).where(Holding.instrument_id == payload.instrument_id)
    )
    if row is None:
        row = Holding(
            instrument_id=payload.instrument_id,
            quantity=payload.quantity,
            average_cost=payload.average_cost,
            note=payload.note,
        )
        db.add(row)
    else:
        row.quantity = payload.quantity
        row.average_cost = payload.average_cost
        row.note = payload.note
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id}


@router.delete("/{holding_id}")
def delete_holding(holding_id: int, db=Depends(get_session)):
    row = db.get(Holding, holding_id)
    if row is None:
        raise HTTPException(404, "holding not found")
    db.delete(row)
    db.commit()
    return {"ok": True}

