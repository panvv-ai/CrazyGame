def test_import_package():
    import marketdata
    assert marketdata.__version__ == "2.0.0"


def test_public_api_exports():
    from marketdata import (
        MarketData,
        Quote,
        SourceConfig,
        StaticConfigProvider,
        Symbol,
    )
    assert MarketData is not None and Symbol is not None and Quote is not None
    assert SourceConfig is not None and StaticConfigProvider is not None
