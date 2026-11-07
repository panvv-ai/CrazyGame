"""Vendor abstraction: one provider parses into normalized quote/bar types."""

from __future__ import annotations

from abc import ABC, abstractmethod

from marketdata.symbol import Symbol


class Vendor(ABC):
    #: 注册名,与 SourceConfig.vendor / DataSource.provider 对齐
    name: str = ""
    #: 支持的市场集合(空集=全部);Engine 会按市场过滤
    supports_markets: frozenset[str] = frozenset()

    @abstractmethod
    def fetch(self, symbols: list[Symbol], config: dict) -> list:
        """抓取并解析。失败应抛异常(Engine 捕获后转移),空结果返回 []。"""
        ...


class QuoteVendor(Vendor):
    """报价 vendor:fetch 返回 list[Quote]。"""


class KlineVendor(Vendor):
    """K 线 vendor:fetch 返回 list[Bar]。单 symbol。"""
