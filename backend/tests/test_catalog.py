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

