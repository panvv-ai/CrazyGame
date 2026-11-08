"""投资标的代码与交易属性的统一识别规则。"""

from __future__ import annotations

_LISTED_FUND_PREFIXES = ("5", "15", "16", "18")


def is_mainland_listed_fund_code(symbol: str) -> bool:
    """判断代码是否属于沪深场内基金代码段。

    上交所场内基金以 5 开头；深交所 ETF 以 159 开头，LOF 以 16 开头，
    老式封闭式基金使用 18 开头。该规则只用于六位数字代码，不会把美股
    字母代码误判为基金。
    """
    code = symbol.strip()
    return (
        len(code) == 6
        and code.isdigit()
        and code.startswith(_LISTED_FUND_PREFIXES)
    )


def canonical_instrument_fields(
    symbol: str,
    market: str,
    asset_type: str,
) -> tuple[str, str, str, str]:
    """返回标的正确的市场、资产类型、币种和行情模式。

    场内基金必须归属 A 股市场并使用上市行情。即使旧缓存或异常客户端提交了
    ``FUND/open_end_fund``、甚至 ``US/stock``，也在这里统一纠正。
    """
    if is_mainland_listed_fund_code(symbol):
        return "CN", "listed_etf", "CNY", "realtime"
    currency = "HKD" if market == "HK" else "USD" if market == "US" else "CNY"
    quote_mode = "estimated" if asset_type == "open_end_fund" else "realtime"
    return market, asset_type, currency, quote_mode
