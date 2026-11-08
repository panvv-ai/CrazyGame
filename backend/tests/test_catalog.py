import pytest
from src.crazygame.providers.fund_collector import fetch_fund_performance
from src.crazygame.services.catalog import classify_search_item


def test_classifies_a_share_stock():
    item = {
        "Code": "600519",
        "Name": "贵州茅台",
        "Classify": "AStock",
        "SecurityTypeName": "沪A",
    }

    result = classify_search_item(item)

    assert result is not None
    assert result.market == "CN"
    assert result.asset_type == "stock"
    assert result.currency == "CNY"
    assert result.quote_mode == "realtime"


def test_classifies_mainland_listed_etf():
    item = {
        "Code": "510300",
        "Name": "沪深300ETF",
        "Classify": "ETF",
        "SecurityTypeName": "ETF",
    }

    result = classify_search_item(item)

    assert result is not None
    assert result.market == "CN"
    assert result.asset_type == "listed_etf"


@pytest.mark.parametrize(
    ("code", "name", "market_type", "quote_id"),
    [
        ("515070", "人工智能ETF华夏", "1", "1.515070"),
        ("588200", "科创芯片ETF嘉实", "1", "1.588200"),
        ("159915", "创业板ETF易方达", "2", "0.159915"),
        ("161130", "纳斯达克100LOF", "2", "0.161130"),
    ],
)
def test_classifies_eastmoney_exchange_funds_from_real_market_fields(
    code, name, market_type, quote_id
):
    item = {
        "Code": code,
        "Name": name,
        "Classify": "Fund",
        "MarketType": market_type,
        "SecurityTypeName": "基金",
        "SecurityType": "8",
        "QuoteID": quote_id,
    }

    result = classify_search_item(item)

    assert result is not None
    assert result.symbol == code
    assert result.market == "CN"
    assert result.asset_type == "listed_etf"
    assert result.currency == "CNY"
    assert result.quote_mode == "realtime"


def test_real_open_end_fund_stays_outside_exchange():
    item = {
        "Code": "110022",
        "Name": "易方达消费行业股票",
        "Classify": "OTCFUND",
        "MarketType": "6",
        "SecurityTypeName": "基金",
        "SecurityType": "17",
        "QuoteID": "150.110022",
    }

    result = classify_search_item(item)

    assert result is not None
    assert result.market == "FUND"
    assert result.asset_type == "open_end_fund"


def test_classifies_open_end_fund():
    item = {
        "Code": "000001",
        "Name": "华夏成长混合",
        "Classify": "Fund",
        "SecurityTypeName": "开放式基金",
    }

    result = classify_search_item(item)

    assert result is not None
    assert result.market == "FUND"
    assert result.asset_type == "open_end_fund"
    assert result.quote_mode == "estimated"


def test_classifies_hong_kong_stock():
    item = {
        "Code": "00700",
        "Name": "腾讯控股",
        "Classify": "HKStock",
        "SecurityTypeName": "港股",
    }

    result = classify_search_item(item)

    assert result is not None
    assert result.market == "HK"
    assert result.currency == "HKD"


def test_fund_collector_is_self_contained():
    assert callable(fetch_fund_performance)

