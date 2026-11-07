"""Supported quote and daily-line vendors."""

from __future__ import annotations

from marketdata.vendors.eastmoney import EastmoneyQuoteVendor
from marketdata.vendors.kline import (
    EastmoneyKlineVendor,
    StooqKlineVendor,
    TencentKlineVendor,
)
from marketdata.vendors.sina import SinaQuoteVendor
from marketdata.vendors.tencent import TencentQuoteVendor

VENDOR_CLASSES_BY_TYPE: dict[str, dict[str, type]] = {
    "quote": {
        "tencent": TencentQuoteVendor,
        "sina": SinaQuoteVendor,
        "eastmoney": EastmoneyQuoteVendor,
    },
    "kline": {
        "tencent": TencentKlineVendor,
        "eastmoney": EastmoneyKlineVendor,
        "stooq": StooqKlineVendor,
    },
}

PACKAGE_VENDORS_BY_TYPE: dict[str, frozenset[str]] = {
    datatype: frozenset(classes)
    for datatype, classes in VENDOR_CLASSES_BY_TYPE.items()
}


def build_vendors(datatype: str) -> dict[str, object]:
    return {
        name: vendor_class()
        for name, vendor_class in VENDOR_CLASSES_BY_TYPE.get(datatype, {}).items()
    }
