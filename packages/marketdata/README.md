# marketdata

Small, dependency-light market data engine used by PanWatchDIY v2.

## Scope

- Batch quotes for A-shares, Hong Kong, and US stocks.
- Daily lines for long-term charts.
- Index quotes and selected index lines.
- Provider priority, fallback, short quote cache, and health metrics.

The package intentionally does not include news, fundamentals, capital flow, dragon-tiger lists, or other research feeds.

## Providers

| Type | Providers |
|---|---|
| Quote | Tencent, Sina, Eastmoney |
| Daily line | Tencent, Eastmoney, Stooq |

For A-shares, Tencent is primary and Eastmoney is fallback. For Hong Kong and US symbols, Tencent is primary and Sina is a quote fallback.

These are public site endpoints, not licensed exchange feeds. They have no SLA and can be delayed, rate-limited, or changed.

## Usage

```python
from marketdata import MarketData, SourceConfig, StaticConfigProvider

market = MarketData(
    StaticConfigProvider(
        {
            "quote": [
                SourceConfig(vendor="tencent", priority=0),
                SourceConfig(vendor="sina", priority=5),
            ],
            "kline": [
                SourceConfig(vendor="tencent", priority=0),
                SourceConfig(vendor="eastmoney", priority=5),
            ],
        }
    )
)

quotes = market.quotes(["600519", "00700", "AAPL"])
bars = market.klines("600519", market="CN", days=365)
```

## Tests

```bash
python -m pytest packages/marketdata/tests -q
```
