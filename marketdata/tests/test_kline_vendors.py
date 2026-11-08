import marketdata.vendors.kline as kv
from marketdata.symbol import Symbol
from marketdata.types import Bar


def test_tencent_kline_parses(monkeypatch):
    js = 'kline_dayqfq={"data":{"sh600519":{"day":[["2026-07-01","1","3","4","0.5","100"],["2026-07-02","3","5","6","2","200"]]}}};'
    monkeypatch.setattr(kv, "market_get", lambda *a, **k: js)
    out = kv.TencentKlineVendor().fetch([Symbol.parse("600519")], {"days": 60})
    assert len(out) == 2 and isinstance(out[0], Bar)
    assert out[0].date == "2026-07-01" and out[0].close == 3.0 and out[1].volume == 200.0


def test_eastmoney_kline_parses(monkeypatch):
    payload = {"data": {"klines": ["2026-07-01,1,3,4,0.5,100", "2026-07-02,3,5,6,2,200"]}}
    monkeypatch.setattr(kv, "market_get", lambda *a, **k: payload)
    out = kv.EastmoneyKlineVendor().fetch([Symbol.parse("600519")], {"days": 60})
    assert len(out) == 2 and out[1].high == 6.0


def test_eastmoney_kline_supports_us_symbols(monkeypatch):
    captured = {}
    payload = {
        "data": {
            "klines": [
                "2026-11-05,180,185,187,179,1000",
                "2026-11-06,185,186.64,188,184,1200",
            ]
        }
    }

    def fake_market_get(*args, **kwargs):
        captured.update(kwargs)
        return payload

    monkeypatch.setattr(kv, "market_get", fake_market_get)
    vendor = kv.EastmoneyKlineVendor()

    out = vendor.fetch([Symbol.parse("NVDA", market="US")], {"days": 365})

    assert "US" in vendor.supports_markets
    assert captured["params"]["secid"] == "105.NVDA"
    assert len(out) == 2
    assert out[-1].close == 186.64


def test_stooq_kline_parses(monkeypatch):
    csv = "Date,Open,High,Low,Close,Volume\n2026-07-01,1,4,0.5,3,100\n2026-07-02,3,6,2,5,200\n"
    monkeypatch.setattr(kv, "market_get", lambda *a, **k: csv)
    out = kv.StooqKlineVendor().fetch([Symbol.parse("AAPL")], {})
    assert len(out) == 2 and out[0].close == 3.0 and out[1].close == 5.0


def test_stooq_kline_uses_short_single_attempt_timeout(monkeypatch):
    captured = {}

    def fake_market_get(*args, **kwargs):
        captured.update(kwargs)
        return ""

    monkeypatch.setattr(kv, "market_get", fake_market_get)
    kv.StooqKlineVendor().fetch([Symbol.parse("AAPL")], {})

    assert captured["timeout"] <= 4
    assert captured["retries"] == 0
