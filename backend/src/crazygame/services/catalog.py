from __future__ import annotations

from dataclasses import dataclass

import httpx

from src.crazygame.domain.instruments import is_mainland_listed_fund_code


class InstrumentSearchUnavailable(RuntimeError):
    """外部搜索源在重试后仍不可用时抛出的受控领域异常。"""


@dataclass(frozen=True)
class InstrumentCandidate:
    """搜索接口返回并完成标准化后的候选标的。"""

    symbol: str
    name: str
    market: str
    asset_type: str
    currency: str
    quote_mode: str


def _normalize_symbol(raw: str, market: str) -> str:
    """去除交易所前缀并统一港股、场外基金代码长度。"""
    code = raw.strip().upper()
    for prefix in ("SH", "SZ", "BJ", "US", "HK"):
        if code.startswith(prefix):
            code = code[len(prefix) :]
            break
    if "." in code:
        code = code.split(".", 1)[0]
    if market == "HK":
        code = code.zfill(5)
    if market == "FUND":
        code = code.zfill(6)
    return code


def classify_search_item(item: dict) -> InstrumentCandidate | None:
    """把东方财富搜索原始行分类为股票、场内 ETF 或场外基金。

    无法可靠判断资产类型时返回 None，宁可少收录也不把错误类型写入自选。
    """
    classify = str(item.get("Classify") or "").strip()
    security_type = str(item.get("SecurityTypeName") or "").strip()
    market_type = str(item.get("MarketType") or "").strip()
    quote_id = str(item.get("QuoteID") or "").strip()
    raw_code = str(item.get("Code") or "").strip()
    if not raw_code:
        return None

    is_exchange_fund = (
        classify == "Fund"
        and (
            market_type in {"1", "2"}
            or quote_id.startswith(("0.", "1."))
            or is_mainland_listed_fund_code(raw_code)
        )
    )
    is_etf = (
        classify.upper() == "ETF"
        or "ETF" in security_type.upper()
        or is_exchange_fund
    )
    is_fund = (
        classify in {"Fund", "ETF", "OTCFUND"}
        or "基金" in security_type
    )
    if is_fund:
        if is_etf:
            return InstrumentCandidate(
                symbol=_normalize_symbol(raw_code, "CN"),
                name=str(item.get("Name") or raw_code),
                market="CN",
                asset_type="listed_etf",
                currency="CNY",
                quote_mode="realtime",
            )
        return InstrumentCandidate(
            symbol=_normalize_symbol(raw_code, "FUND"),
            name=str(item.get("Name") or raw_code),
            market="FUND",
            asset_type="open_end_fund",
            currency="CNY",
            quote_mode="estimated",
        )

    if (
        classify in {"AStock", "BJStock"}
        or any(marker in security_type for marker in ("沪", "深", "北"))
        or raw_code.endswith(".BJ")
        or raw_code.startswith("BJ")
    ):
        return InstrumentCandidate(
            symbol=_normalize_symbol(raw_code, "CN"),
            name=str(item.get("Name") or raw_code),
            market="CN",
            asset_type="stock",
            currency="CNY",
            quote_mode="realtime",
        )
    if classify == "HKStock" or "港" in security_type:
        return InstrumentCandidate(
            symbol=_normalize_symbol(raw_code, "HK"),
            name=str(item.get("Name") or raw_code),
            market="HK",
            asset_type="stock",
            currency="HKD",
            quote_mode="realtime",
        )
    if classify == "UsStock" or "美" in security_type:
        type_us = str(item.get("TypeUS") or "")
        if type_us and type_us not in {"1", "2", "3"}:
            return None
        return InstrumentCandidate(
            symbol=_normalize_symbol(raw_code, "US"),
            name=str(item.get("Name") or raw_code),
            market="US",
            asset_type="stock",
            currency="USD",
            quote_mode="realtime",
        )
    return None


def search_instruments(
    query: str,
    *,
    market: str = "",
    asset_type: str = "",
    limit: int = 20,
) -> list[InstrumentCandidate]:
    """跨市场搜索标的，并按市场、资产类型过滤后去重。"""
    if not query.strip():
        return []
    last_error: Exception | None = None
    rows = []
    for _attempt in range(2):
        try:
            response = httpx.get(
                "https://searchapi.eastmoney.com/api/suggest/get",
                params={
                    "input": query.strip(),
                    "type": 14,
                    "count": max(limit * 5, 20),
                },
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            response.raise_for_status()
            rows = (
                response.json()
                .get("QuotationCodeTable", {})
                .get("Data", [])
            )
            break
        except (httpx.HTTPError, ValueError) as error:
            last_error = error
    else:
        raise InstrumentSearchUnavailable(
            "instrument search source is unavailable"
        ) from last_error

    output: list[InstrumentCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        candidate = classify_search_item(row)
        if candidate is None:
            continue
        if market and candidate.market != market:
            continue
        if asset_type and candidate.asset_type != asset_type:
            continue
        key = (candidate.symbol, candidate.market, candidate.asset_type)
        if key in seen:
            continue
        seen.add(key)
        output.append(candidate)
        if len(output) >= limit:
            break
    return output

