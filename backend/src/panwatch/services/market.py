from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from src.panwatch.core.calendar import EARLY_CLOSES, is_trading_day
from src.panwatch.domain.models import Instrument

MARKET_TIMEZONES = {
    "CN": ZoneInfo("Asia/Shanghai"),
    "HK": ZoneInfo("Asia/Hong_Kong"),
    "US": ZoneInfo("America/New_York"),
    "FUND": ZoneInfo("Asia/Shanghai"),
}

MARKET_SESSIONS = {
    "CN": ((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))),
    "HK": ((time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))),
    "US": ((time(9, 30), time(16, 0)),),
    "FUND": ((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))),
}


def is_market_open(market: str, moment: datetime) -> bool:
    market_code = market.upper()
    timezone = MARKET_TIMEZONES.get(market_code)
    if timezone is None:
        return False
    local = moment.astimezone(timezone)
    if not is_trading_day(market_code, local.date()):
        return False
    sessions = list(MARKET_SESSIONS[market_code])
    early_close = EARLY_CLOSES.get((market_code, local.date()))
    if early_close is not None:
        sessions = [
            (start, min(end, time(early_close, 0)))
            for start, end in sessions
            if start < time(early_close, 0)
        ]
    return any(start <= local.time() <= end for start, end in sessions)


@dataclass(frozen=True)
class QuoteSnapshot:
    symbol: str
    name: str
    market: str
    current_price: float | None
    change_pct: float | None
    previous_close: float | None
    as_of: str
    source: str
    freshness: str

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "market": self.market,
            "current_price": self.current_price,
            "change_pct": self.change_pct,
            "previous_close": self.previous_close,
            "as_of": self.as_of,
            "source": self.source,
            "freshness": self.freshness,
        }


class MarketService:
    def fetch_quotes(self, instruments: list[Instrument]) -> dict[tuple[str, str], QuoteSnapshot]:
        groups: dict[str, list[Instrument]] = {}
        for instrument in instruments:
            key = "FUND" if instrument.market == "FUND" else instrument.market
            groups.setdefault(key, []).append(instrument)

        output: dict[tuple[str, str], QuoteSnapshot] = {}
        for market, items in groups.items():
            if market == "FUND":
                from src.panwatch.providers.fund_quotes import _fetch_fund_quotes

                rows = _fetch_fund_quotes([item.symbol for item in items])
                by_symbol = {str(row.get("symbol")): row for row in rows}
                for item in items:
                    row = by_symbol.get(item.symbol)
                    if row:
                        output[(item.symbol, item.market)] = self._fund_quote(item, row)
                continue

            from src.panwatch.services.marketdata import get_marketdata_client

            quotes = get_marketdata_client().quotes(
                [item.symbol for item in items],
                market=market,
            )
            by_symbol = {str(quote.symbol): quote for quote in quotes}
            for item in items:
                quote = by_symbol.get(item.symbol)
                if quote:
                    output[(item.symbol, item.market)] = self._listed_quote(item, quote)
        return output

    def _listed_quote(self, instrument: Instrument, quote) -> QuoteSnapshot:
        timestamp = quote.timestamp
        if isinstance(timestamp, datetime):
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(
                    tzinfo=MARKET_TIMEZONES.get(instrument.market, ZoneInfo("UTC"))
                )
            as_of = timestamp.isoformat(timespec="seconds")
        else:
            as_of = str(timestamp or "")
        return QuoteSnapshot(
            symbol=instrument.symbol,
            name=str(quote.name or instrument.name),
            market=instrument.market,
            current_price=_float(quote.current_price),
            change_pct=_float(quote.change_pct),
            previous_close=_float(quote.prev_close),
            as_of=as_of,
            source="marketdata",
            freshness="live",
        )

    def _fund_quote(self, instrument: Instrument, row: dict) -> QuoteSnapshot:
        estimated = row.get("current_price") is not None
        current = _float(row.get("current_price"))
        previous = _float(row.get("prev_close"))
        if current is None:
            current = previous
        as_of = str(row.get("gztime") or row.get("jzrq") or "")
        return QuoteSnapshot(
            symbol=instrument.symbol,
            name=str(row.get("name") or instrument.name),
            market=instrument.market,
            current_price=current,
            change_pct=_float(row.get("change_pct")),
            previous_close=previous,
            as_of=as_of,
            source="eastmoney_fund",
            freshness="estimated" if estimated else "official_nav",
        )

    def fetch_daily_points(
        self,
        instrument: Instrument,
        *,
        days: int = 365,
    ) -> list[tuple[date, float]]:
        if instrument.asset_type == "open_end_fund":
            from src.panwatch.providers.fund_collector import fetch_fund_performance

            payload = fetch_fund_performance(instrument.symbol)
            points: list[tuple[date, float]] = []
            for point in payload.get("points", []):
                try:
                    point_date = datetime.fromtimestamp(point["ts"] / 1000).date()
                    points.append((point_date, float(point["value"])))
                except (KeyError, TypeError, ValueError):
                    continue
            cutoff = date.today().fromordinal(date.today().toordinal() - days)
            return [(day, value) for day, value in points if day >= cutoff]

        from src.panwatch.services.marketdata import get_marketdata_client

        bars = get_marketdata_client().klines(
            instrument.symbol,
            market=instrument.market,
            days=days,
            min_count=min(days, 120),
        )
        points = []
        for bar in bars:
            try:
                points.append((date.fromisoformat(bar.date), float(bar.close)))
            except (TypeError, ValueError):
                continue
        cutoff = date.today().fromordinal(date.today().toordinal() - days)
        return [(day, value) for day, value in points if day >= cutoff]


def _float(value) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

