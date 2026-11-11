from __future__ import annotations

import math
from statistics import pstdev

from marketdata.types import Bar


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (period + 1)
    output = [values[0]]
    for value in values[1:]:
        output.append(alpha * value + (1 - alpha) * output[-1])
    return output


def _rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) <= period:
        return None
    changes = [current - previous for previous, current in zip(values, values[1:])]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        average_gain = (average_gain * (period - 1) + gain) / period
        average_loss = (average_loss * (period - 1) + loss) / period
    if average_loss == 0:
        return 100.0
    relative_strength = average_gain / average_loss
    return 100 - 100 / (1 + relative_strength)


def _macd(values: list[float]) -> dict[str, float | None]:
    if len(values) < 26:
        return {"dif": None, "dea": None, "bar": None}
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    dif_values = [fast - slow for fast, slow in zip(ema12, ema26)]
    dea_values = _ema(dif_values, 9)
    dif = dif_values[-1]
    dea = dea_values[-1]
    return {
        "dif": round(dif, 4),
        "dea": round(dea, 4),
        "bar": round((dif - dea) * 2, 4),
    }


def _moving_average(values: list[float], period: int) -> float | None:
    return round(sum(values[-period:]) / period, 4) if len(values) >= period else None


def _change_pct(values: list[float], period: int) -> float | None:
    if len(values) <= period or values[-period - 1] == 0:
        return None
    return round((values[-1] / values[-period - 1] - 1) * 100, 2)


def _max_drawdown_pct(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1)
    return round(worst * 100, 2)


def _support_resistance(bars: list[Bar]) -> tuple[float | None, float | None]:
    if not bars:
        return None, None
    current = bars[-1].close
    recent = bars[-60:]
    lows = [bar.low for bar in recent if bar.low <= current]
    highs = [bar.high for bar in recent if bar.high >= current]
    support = max(lows) if lows else min(bar.low for bar in recent)
    resistance = min(highs) if highs else max(bar.high for bar in recent)
    if support == resistance:
        resistance = support * 1.01
    return round(support, 4), round(resistance, 4)


def build_technical_snapshot(bars: list[Bar]) -> dict:
    """Build deterministic technical evidence from at most 250 daily bars."""
    selected = bars[-250:]
    closes = [float(bar.close) for bar in selected]
    ma_values = {
        f"ma{period}": _moving_average(closes, period)
        for period in (5, 10, 20, 60)
    }
    ma5 = ma_values["ma5"]
    ma10 = ma_values["ma10"]
    ma20 = ma_values["ma20"]
    if None in (ma5, ma10, ma20):
        alignment = "unknown"
    elif ma5 > ma10 > ma20:
        alignment = "bullish"
    elif ma5 < ma10 < ma20:
        alignment = "bearish"
    else:
        alignment = "mixed"

    limitations = []
    if len(selected) < 60:
        limitations.append("history_under_60_days")

    volumes = [float(bar.volume) for bar in selected]
    recent_volume = _mean(volumes[-5:]) if len(volumes) >= 5 else None
    baseline_volume = _mean(volumes[-25:-5]) if len(volumes) >= 25 else None
    volume_ratio = (
        round(recent_volume / baseline_volume, 2)
        if recent_volume is not None and baseline_volume
        else None
    )

    daily_returns = [
        current / previous - 1
        for previous, current in zip(closes, closes[1:])
        if previous
    ]
    volatility = (
        round(pstdev(daily_returns) * math.sqrt(252) * 100, 2)
        if len(daily_returns) >= 2
        else None
    )
    support, resistance = _support_resistance(selected)

    return {
        "bar_count": len(selected),
        "ma": {
            **ma_values,
            "alignment": alignment,
        },
        "rsi14": round(rsi, 2) if (rsi := _rsi(closes)) is not None else None,
        "macd": _macd(closes),
        "returns_pct": {
            "5d": _change_pct(closes, 5),
            "20d": _change_pct(closes, 20),
            "60d": _change_pct(closes, 60),
        },
        "volatility_annualized_pct": volatility,
        "max_drawdown_pct": _max_drawdown_pct(closes),
        "volume_ratio_20d": volume_ratio,
        "support": support,
        "resistance": resistance,
        "limitations": limitations,
    }
