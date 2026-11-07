"""Request, quote, daily-bar, and response types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Request:
    symbols: tuple[str, ...] = ()
    market: str = "CN"
    timeframe: str = "day"
    limit: int = 120
    since_hours: int = 12
    extra: tuple[tuple[str, Any], ...] = ()

    def cache_key(self, datatype: str) -> str:
        symbols = ",".join(self.symbols)
        extra = ",".join(f"{key}={value}" for key, value in self.extra)
        return (
            f"{datatype}|{self.market}|{self.timeframe}|{self.limit}|"
            f"{self.since_hours}|{symbols}|{extra}"
        )


@dataclass
class Quote:
    symbol: str
    market: str
    current_price: float
    name: str = ""
    prev_close: float | None = None
    open_price: float | None = None
    high_price: float | None = None
    low_price: float | None = None
    change_amount: float | None = None
    change_pct: float | None = None
    volume: float | None = None
    turnover: float | None = None
    turnover_rate: float | None = None
    volume_ratio: float | None = None
    pe_ratio: float | None = None
    circulating_market_value: float | None = None
    total_market_value: float | None = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Bar:
    date: str
    open: float
    close: float
    high: float
    low: float
    volume: float = 0.0


@dataclass
class Response:
    ok: bool
    data: Any = None
    error: str = ""
    vendor: str = ""
    latency_ms: int = 0

    @property
    def is_empty(self) -> bool:
        if self.data is None:
            return True
        if isinstance(self.data, (list, tuple, dict, set)) and len(self.data) == 0:
            return True
        return False
