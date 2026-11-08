from src.crazygame.domain.instruments import (
    canonical_instrument_fields,
    is_mainland_listed_fund_code,
)


def test_recognizes_exchange_listed_fund_code_families():
    for code in ("510300", "515070", "588200", "159915", "161130"):
        assert is_mainland_listed_fund_code(code)

    for code in ("110022", "000001", "600519", "AAPL", "00700"):
        assert not is_mainland_listed_fund_code(code)


def test_canonicalizes_wrong_market_and_asset_type_for_listed_funds():
    assert canonical_instrument_fields("515070", "US", "stock") == (
        "CN",
        "listed_etf",
        "CNY",
        "realtime",
    )
    assert canonical_instrument_fields("588200", "FUND", "open_end_fund") == (
        "CN",
        "listed_etf",
        "CNY",
        "realtime",
    )
