from __future__ import annotations

from marketdata import MarketData, SourceConfig, StaticConfigProvider

_MARKET_DATA: MarketData | None = None


def get_marketdata_client() -> MarketData:
    """返回进程级行情客户端单例，复用缓存和供应商指标。"""
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

