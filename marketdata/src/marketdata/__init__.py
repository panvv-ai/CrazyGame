"""Multi-market quote and daily-line engine with provider fallback."""

from marketdata.client import MarketData
from marketdata.defaults import InMemoryMetricsSink, StaticConfigProvider
from marketdata.errors import MarketDataError, VendorError
from marketdata.http import capture_errors, record_error
from marketdata.ports import ConfigProvider, MetricsSink, SourceConfig
from marketdata.registry import PACKAGE_VENDORS_BY_TYPE
from marketdata.symbol import Market, Symbol
from marketdata.types import Bar, Quote, Request, Response

__version__ = "1.0.0"

__all__ = [
    "MarketData",
    "Symbol",
    "Market",
    "Bar",
    "Quote",
    "Request",
    "Response",
    "SourceConfig",
    "ConfigProvider",
    "MetricsSink",
    "StaticConfigProvider",
    "InMemoryMetricsSink",
    "PACKAGE_VENDORS_BY_TYPE",
    "capture_errors",
    "record_error",
    "MarketDataError",
    "VendorError",
    "__version__",
]
