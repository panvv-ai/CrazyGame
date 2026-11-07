"""Object-style entry point for list-market quotes and daily lines."""

from __future__ import annotations

from marketdata.cache import TTLCache
from marketdata.defaults import InMemoryMetricsSink
from marketdata.engine import Engine
from marketdata.ports import ConfigProvider, MetricsSink
from marketdata.registry import build_vendors
from marketdata.symbol import Symbol
from marketdata.types import Quote, Request

INDEX_SECID: dict[str, str] = {
    "000300": "1.000300",
    "000001": "1.000001",
    "399001": "0.399001",
    "399006": "0.399006",
    "HSI": "100.HSI",
}


class MarketData:
    def __init__(self, config: ConfigProvider, metrics: MetricsSink | None = None):
        self.config = config
        self.metrics = metrics or InMemoryMetricsSink()
        self._quote_engine = Engine(
            datatype="quote",
            vendors=build_vendors("quote"),
            config=config,
            metrics=self.metrics,
            cache=TTLCache(default_ttl_sec=5.0),
            default_ttl=5.0,
        )
        self._kline_engine = Engine(
            datatype="kline",
            vendors=build_vendors("kline"),
            config=config,
            metrics=self.metrics,
            cache=TTLCache(default_ttl_sec=0.0),
            default_ttl=0.0,
        )

    def quotes(
        self,
        symbols: list[str | Symbol],
        *,
        market: str | None = None,
    ) -> list[Quote]:
        groups: dict[str, list[Symbol]] = {}
        for raw in symbols:
            symbol = raw if isinstance(raw, Symbol) else Symbol.parse(raw, market)
            groups.setdefault(symbol.market.value, []).append(symbol)

        output: list[Quote] = []
        for market_code, market_symbols in groups.items():
            request = Request(
                symbols=tuple(symbol.code for symbol in market_symbols),
                market=market_code,
            )
            response = self._quote_engine.fetch(request)
            if response.ok and response.data:
                output.extend(response.data)
        return output

    def klines(
        self,
        symbol: str,
        *,
        market: str,
        days: int = 120,
        min_count: int = 1,
    ) -> list:
        request = Request(
            symbols=(symbol,),
            market=market,
            timeframe="day",
            limit=days,
            extra=(("days", days),),
        )
        response = self._kline_engine.fetch(
            request,
            min_count=min_count,
            cache_ttl_sec=0,
        )
        return response.data or []

    def index_quotes(self, tencent_symbols: list[str]) -> list[dict]:
        from marketdata.vendors.tencent import fetch_raw

        return fetch_raw(list(tencent_symbols)) if tencent_symbols else []

    def index_klines(self, code: str, *, market: str, days: int = 120) -> list:
        secid = INDEX_SECID.get(str(code).strip()) or INDEX_SECID.get(
            str(code).strip().upper()
        )
        if not secid:
            return []
        from marketdata.vendors.kline import fetch_eastmoney_kline

        return fetch_eastmoney_kline(secid, days)

    def health(self) -> dict[str, dict]:
        return self.metrics.snapshot()
