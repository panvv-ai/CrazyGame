from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.panwatch.api.dependencies import get_session
from src.panwatch.api.serializers import instrument_dict
from src.panwatch.domain.models import Holding, Instrument

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

