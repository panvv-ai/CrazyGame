from __future__ import annotations

from marketdata import MarketData, SourceConfig, StaticConfigProvider

_MARKET_DATA: MarketData | None = None


def get_v2_market_data() -> MarketData:
    global _MARKET_DATA
    if _MARKET_DATA is None:
        _MARKET_DATA = MarketData(
            config=StaticConfigProvider(
                {
                    "quote": [
                        SourceConfig(vendor="tencent", priority=0),
                        SourceConfig(vendor="eastmoney", priority=3),
                        SourceConfig(vendor="sina", priority=5),
                    ],
                    "kline": [
                        SourceConfig(vendor="tencent", priority=0),
                        SourceConfig(vendor="eastmoney", priority=5),
                        SourceConfig(vendor="stooq", priority=15),
                    ],
                }
            )
        )
    return _MARKET_DATA

