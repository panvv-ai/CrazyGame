from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from src.crazygame.core.timeutils import iso_utc
from src.crazygame.domain.models import AIChatMessage, AIChatSession, Instrument
from src.crazygame.services.catalog import search_instruments

_COMMON_ENGLISH_TOKENS = {
    "AI",
    "ALL",
    "AND",
    "ARE",
    "BUY",
    "CAN",
    "FOR",
    "HOW",
    "IS",
    "IT",
    "NOW",
    "OF",
    "OR",
    "SELL",
    "THE",
    "THIS",
    "TO",
    "TREND",
    "WHAT",
    "WHY",
}


@dataclass
class PreparedChatTurn:
    request_id: str
    session_id: str
    instrument: Instrument | None
    candidates: list[dict]
    history: list[dict]
    message: str


def _instrument_dict(instrument: Instrument) -> dict:
    return {
        "id": instrument.id,
        "instrument_id": instrument.id,
        "symbol": instrument.symbol,
        "name": instrument.name,
        "market": instrument.market,
        "asset_type": instrument.asset_type,
        "currency": instrument.currency,
        "quote_mode": instrument.quote_mode,
    }


class AIChatService:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def _search_query(message: str) -> str | None:
        numeric = re.search(
            r"(?<![A-Za-z0-9])(\d{5,6})(?![A-Za-z0-9])",
            message,
        )
        if numeric:
            return numeric.group(1)
        explicit = re.search(
            r"(?:\$|\bUS[.:])([A-Za-z]{1,5}(?:\.[A-Z])?)",
            message,
            flags=re.IGNORECASE,
        )
        if explicit:
            return explicit.group(1).upper()
        named = re.search(
            r"(?:分析|诊断|看看|研究|问股)\s*([\u4e00-\u9fffA-Za-z0-9·]{2,24})",
            message,
        )
        if named:
            query = named.group(1)
            return None if query.upper() in _COMMON_ENGLISH_TOKENS else query
        uppercase = re.search(
            r"(?<![A-Za-z0-9])([A-Z]{1,5}(?:\.[A-Z])?)(?![A-Za-z0-9])",
            message,
        )
        if uppercase:
            return (
                None
                if uppercase.group(1) in _COMMON_ENGLISH_TOKENS
                else uppercase.group(1)
            )
        text = message.strip()
        if re.fullmatch(r"[A-Za-z]{1,5}(?:\.[A-Z])?", text):
            return None if text.upper() in _COMMON_ENGLISH_TOKENS else text
        if re.search(r"(?<![A-Za-z0-9])[A-Za-z]{1,5}(?![A-Za-z0-9])", text):
            return None
        if 2 <= len(text) <= 24 and not any(
            marker in text
            for marker in (
                "市场",
                "大盘",
                "持仓",
                "提醒",
                "风险",
                "量能",
                "均线",
                "支撑",
                "压力",
                "估值",
                "走势",
                "趋势",
                "建议",
                "怎么看",
                "如何",
            )
        ):
            return text
        return None

    def _candidates_from_message(self, message: str) -> list[dict]:
        query = self._search_query(message)
        if not query:
            return []
        try:
            items = search_instruments(query, limit=8)
        except Exception:
            return []
        return [
            {
                "symbol": item.symbol,
                "name": item.name,
                "market": item.market,
                "asset_type": item.asset_type,
                "currency": item.currency,
                "quote_mode": item.quote_mode,
            }
            for item in items
            if item.asset_type in {"stock", "listed_etf"}
        ]

    def prepare_turn(
        self,
        *,
        message: str,
        session_id: str | None = None,
        instrument_id: int | None = None,
    ) -> PreparedChatTurn:
        text = message.strip()
        if not text:
            raise ValueError("message is required")
        with self.session_factory() as db:
            session = db.get(AIChatSession, session_id) if session_id else None
            if session is None:
                session = AIChatSession(
                    id=session_id or uuid.uuid4().hex,
                    title=text[:60],
                )
                db.add(session)
                db.flush()
            previous_instrument_id = session.active_instrument_id
            history_rows = db.scalars(
                select(AIChatMessage)
                .where(AIChatMessage.session_id == session.id)
                .order_by(AIChatMessage.id.desc())
                .limit(12)
            ).all()
            history = [
                {"role": row.role, "content": row.content}
                for row in reversed(history_rows)
            ]

            instrument = db.get(Instrument, instrument_id) if instrument_id else None
            candidates: list[dict] = []
            if instrument is None:
                candidates = self._candidates_from_message(text)
                if len(candidates) == 1:
                    candidate = candidates[0]
                    instrument = db.scalar(
                        select(Instrument).where(
                            Instrument.symbol == candidate["symbol"],
                            Instrument.market == candidate["market"],
                            Instrument.asset_type == candidate["asset_type"],
                        )
                    )
                    if instrument is None:
                        instrument = Instrument(
                            symbol=candidate["symbol"],
                            name=candidate["name"],
                            market=candidate["market"],
                            asset_type=candidate["asset_type"],
                            currency=candidate["currency"],
                            quote_mode=candidate["quote_mode"],
                        )
                        db.add(instrument)
                        db.flush()
            if instrument is None and not candidates and session.active_instrument_id:
                instrument = db.get(Instrument, session.active_instrument_id)
            if instrument is not None and instrument.asset_type == "open_end_fund":
                instrument = None
                candidates = []

            if instrument is not None:
                session.active_instrument_id = instrument.id
                if (
                    previous_instrument_id is not None
                    and previous_instrument_id != instrument.id
                ):
                    history = []
            session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.add(
                AIChatMessage(
                    session_id=session.id,
                    role="user",
                    content=text,
                )
            )
            db.commit()
            if instrument is not None:
                db.refresh(instrument)
            active = instrument
            session_key = session.id
        return PreparedChatTurn(
            request_id=uuid.uuid4().hex,
            session_id=session_key,
            instrument=active,
            candidates=candidates if active is None else [],
            history=history,
            message=text,
        )

    def save_assistant(
        self,
        session_id: str,
        content: str,
        *,
        tools: list[dict] | None = None,
    ) -> None:
        with self.session_factory() as db:
            session = db.get(AIChatSession, session_id)
            if session is None:
                return
            db.add(
                AIChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=content,
                    metadata_json=json.dumps(
                        {"tools": tools or []},
                        ensure_ascii=False,
                    ),
                )
            )
            session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()

    def list_sessions(self, limit: int = 50) -> list[dict]:
        with self.session_factory() as db:
            sessions = db.scalars(
                select(AIChatSession)
                .order_by(AIChatSession.updated_at.desc(), AIChatSession.id.desc())
                .limit(max(1, min(limit, 100)))
            ).all()
            return [
                {
                    "id": session.id,
                    "title": session.title,
                    "message_count": len(session.messages),
                    "updated_at": iso_utc(session.updated_at),
                    "active_instrument": (
                        _instrument_dict(session.active_instrument)
                        if session.active_instrument
                        else None
                    ),
                }
                for session in sessions
            ]

    def get_session(self, session_id: str) -> dict | None:
        with self.session_factory() as db:
            session = db.get(AIChatSession, session_id)
            if session is None:
                return None
            return {
                "id": session.id,
                "title": session.title,
                "active_instrument": (
                    _instrument_dict(session.active_instrument)
                    if session.active_instrument
                    else None
                ),
                "messages": [
                    {
                        "id": message.id,
                        "role": message.role,
                        "content": message.content,
                        "metadata": json.loads(message.metadata_json or "{}"),
                        "created_at": iso_utc(message.created_at),
                    }
                    for message in session.messages
                ],
            }

    def delete_session(self, session_id: str) -> bool:
        with self.session_factory() as db:
            session = db.get(AIChatSession, session_id)
            if session is None:
                return False
            db.delete(session)
            db.commit()
            return True


def instrument_payload(instrument: Instrument | None) -> dict | None:
    return _instrument_dict(instrument) if instrument is not None else None
