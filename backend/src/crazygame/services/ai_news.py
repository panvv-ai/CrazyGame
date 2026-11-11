from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from src.crazygame.domain.models import AppSetting, MarketIntel, utc_now


@dataclass(frozen=True)
class IntelItem:
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime | None
    relevance_score: int = 0
    relevance_kind: str = "macro"
    relevance_reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "relevance_score": self.relevance_score,
            "relevance_kind": self.relevance_kind,
            "relevance_reasons": list(self.relevance_reasons),
        }


def _normalize_time(value: datetime | None, now: datetime) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=now.tzinfo or timezone.utc)
    return value


def _identity_score(
    item: IntelItem,
    *,
    symbol: str,
    name: str,
    industry: str,
    concepts: list[str],
) -> tuple[int, str, list[str]]:
    title = item.title.casefold()
    summary = item.summary.casefold()
    code = symbol.casefold()
    company = name.casefold()
    score = 0
    direct = False
    reasons: list[str] = []

    if code and code in title:
        score += 55
        direct = True
        reasons.append(f"标题命中代码 {symbol}")
    elif code and code in summary:
        score += 35
        direct = True
        reasons.append(f"摘要命中代码 {symbol}")

    if company and company in title:
        score += 45
        direct = True
        reasons.append(f"标题命中公司名 {name}")
    elif company and company in summary:
        score += 28
        direct = True
        reasons.append(f"摘要命中公司名 {name}")

    sector_terms = [industry, *concepts]
    sector_hit = next(
        (
            term
            for term in sector_terms
            if term and (term.casefold() in title or term.casefold() in summary)
        ),
        None,
    )
    if sector_hit:
        score += 18 if sector_hit.casefold() in title else 10
        reasons.append(f"命中行业或概念 {sector_hit}")

    if direct:
        return score, "direct", reasons
    if sector_hit:
        return score, "sector", reasons
    reasons.append("未命中公司身份，仅作为市场背景")
    return score, "macro", reasons


def _recency_score(published_at: datetime | None, now: datetime) -> int:
    if published_at is None:
        return 0
    age = now - published_at
    if age <= timedelta(hours=6):
        return 16
    if age <= timedelta(days=1):
        return 12
    if age <= timedelta(days=3):
        return 8
    if age <= timedelta(days=7):
        return 4
    return 0


def rank_intel_items(
    items: list[IntelItem],
    *,
    symbol: str,
    name: str,
    industry: str = "",
    concepts: list[str] | None = None,
    now: datetime | None = None,
    limit: int = 8,
) -> list[IntelItem]:
    """Rank explainable stock intelligence and remove stale or duplicate pages."""
    reference_time = now or datetime.now(timezone.utc)
    concept_names = list(concepts or [])
    cutoff = reference_time - timedelta(days=30)
    deduped: dict[str, IntelItem] = {}

    for item in items:
        published_at = _normalize_time(item.published_at, reference_time)
        if published_at is not None and published_at < cutoff:
            continue
        normalized = replace(item, published_at=published_at)
        key = (item.url or f"{item.source}:{item.title}").split("#", 1)[0].rstrip("/")
        existing = deduped.get(key)
        if existing is None or (
            normalized.published_at
            and (
                existing.published_at is None
                or normalized.published_at > existing.published_at
            )
        ):
            deduped[key] = normalized

    category_rank = {"direct": 0, "sector": 1, "macro": 2}
    ranked: list[IntelItem] = []
    for item in deduped.values():
        identity_score, kind, reasons = _identity_score(
            item,
            symbol=symbol,
            name=name,
            industry=industry,
            concepts=concept_names,
        )
        source_bonus = 8 if any(
            marker in item.source.casefold()
            for marker in ("公告", "交易所", "证券时报", "财联社")
        ) else 0
        score = min(
            100,
            identity_score
            + _recency_score(item.published_at, reference_time)
            + source_bonus,
        )
        ranked.append(
            replace(
                item,
                relevance_score=score,
                relevance_kind=kind,
                relevance_reasons=tuple(reasons),
            )
        )

    ranked.sort(
        key=lambda item: (
            category_rank.get(item.relevance_kind, 9),
            -item.relevance_score,
            -(item.published_at.timestamp() if item.published_at else 0),
            urlparse(item.url).netloc,
        )
    )
    return ranked[: max(0, limit)]


def _clean_text(value: object) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", str(value or ""))).strip()


def _china_time(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S:%f", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=timezone(timedelta(hours=8))).astimezone(
                timezone.utc
            )
        except ValueError:
            continue
    return None


def parse_eastmoney_news_jsonp(
    text: str,
    *,
    now: datetime | None = None,
) -> list[IntelItem]:
    stripped = text.strip()
    if stripped and not stripped.startswith(("{", "[")):
        start = stripped.find("(")
        end = stripped.rfind(")")
        if start >= 0 and end > start:
            stripped = stripped[start + 1 : end]
    payload = json.loads(stripped)
    rows = (
        payload.get("result", {})
        .get("cmsArticleWebOld", [])
        if isinstance(payload, dict)
        else []
    )
    return [
        IntelItem(
            title=_clean_text(row.get("title")),
            summary=_clean_text(row.get("content")),
            url=str(row.get("url") or ""),
            source=str(row.get("mediaName") or "东方财富"),
            published_at=_china_time(row.get("date")),
        )
        for row in rows
        if isinstance(row, dict) and _clean_text(row.get("title"))
    ]


def parse_eastmoney_announcements(
    payload: dict,
    *,
    symbol: str,
) -> list[IntelItem]:
    rows = payload.get("data", {}).get("list", []) if isinstance(payload, dict) else []
    output = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = _clean_text(row.get("title") or row.get("title_ch"))
        art_code = str(row.get("art_code") or "").strip()
        if not title or not art_code:
            continue
        output.append(
            IntelItem(
                title=title,
                summary=", ".join(
                    _clean_text(item.get("column_name"))
                    for item in row.get("columns", [])
                    if isinstance(item, dict) and item.get("column_name")
                ),
                url=f"https://data.eastmoney.com/notices/detail/{symbol}/{art_code}.html",
                source="公司公告",
                published_at=_china_time(row.get("notice_date")),
            )
        )
    return output


def parse_eastmoney_tags(payload: dict) -> dict:
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    industry = _clean_text(data.get("f127"))
    concepts = [
        item.strip()
        for item in str(data.get("f129") or "").split(",")
        if item.strip()
    ]
    return {"industry": industry, "concepts": concepts}


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return _china_time(value)


def parse_tavily_results(payload: dict) -> list[IntelItem]:
    return [
        IntelItem(
            title=_clean_text(row.get("title")),
            summary=_clean_text(row.get("content")),
            url=str(row.get("url") or ""),
            source="Tavily",
            published_at=_parse_datetime(row.get("published_date")),
        )
        for row in payload.get("results", [])
        if isinstance(row, dict) and _clean_text(row.get("title"))
    ]


def parse_bocha_results(payload: dict) -> list[IntelItem]:
    rows = (
        payload.get("data", {})
        .get("webPages", {})
        .get("value", [])
    )
    return [
        IntelItem(
            title=_clean_text(row.get("name") or row.get("title")),
            summary=_clean_text(row.get("summary") or row.get("snippet")),
            url=str(row.get("url") or ""),
            source=_clean_text(row.get("siteName")) or "Bocha",
            published_at=_parse_datetime(row.get("datePublished")),
        )
        for row in rows
        if isinstance(row, dict) and _clean_text(row.get("name") or row.get("title"))
    ]


class NewsService:
    """Free Eastmoney intel with a local cache and fail-open degradation."""

    def __init__(
        self,
        session_factory,
        *,
        settings=None,
        secret_box=None,
        timeout_seconds: float = 12.0,
    ):
        self.session_factory = session_factory
        self.settings = settings or {}
        self.secret_box = secret_box
        self.timeout_seconds = timeout_seconds

    def _provider_config(self) -> dict:
        if self.settings:
            return dict(self.settings)
        with self.session_factory() as db:
            row = db.get(AppSetting, "news")
            if row is None:
                return {
                    "enabled": True,
                    "provider": "eastmoney",
                    "api_key": "",
                }
            try:
                payload = json.loads(row.value)
            except (TypeError, ValueError, json.JSONDecodeError):
                payload = {}
        key = str(payload.get("api_key") or "")
        if key and self.secret_box is not None:
            try:
                key = self.secret_box.decrypt(key)
            except Exception:
                key = ""
        return {
            "enabled": bool(payload.get("enabled", True)),
            "provider": str(payload.get("provider") or "eastmoney"),
            "api_key": key,
        }

    def _secid(self, instrument) -> str:
        if instrument.market == "HK":
            return f"116.{instrument.symbol}"
        if instrument.market == "US":
            return f"105.{instrument.symbol}"
        from marketdata.symbol import _cn_exchange

        return f"{'1' if _cn_exchange(instrument.symbol) == 'sh' else '0'}.{instrument.symbol}"

    def _fetch_tags(self, instrument) -> dict:
        response = httpx.get(
            "https://push2.eastmoney.com/api/qt/stock/get",
            params={"secid": self._secid(instrument), "fields": "f127,f129"},
            headers={"User-Agent": "CrazyGame/1.0"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return parse_eastmoney_tags(response.json())

    def _search_news(self, keyword: str) -> list[IntelItem]:
        param = json.dumps(
            {
                "uid": "",
                "keyword": keyword,
                "type": ["cmsArticleWebOld"],
                "client": "web",
                "clientType": "web",
                "pageIndex": 1,
                "pageSize": 20,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        response = httpx.get(
            "https://search-api-web.eastmoney.com/search/jsonp",
            params={"cb": "crazygame", "param": param},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return parse_eastmoney_news_jsonp(response.text)

    def _fetch_announcements(self, instrument) -> list[IntelItem]:
        response = httpx.get(
            "https://np-anotice-stock.eastmoney.com/api/security/ann",
            params={
                "sr": -1,
                "page_size": 20,
                "page_index": 1,
                "ann_type": "A",
                "client_source": "web",
                "stock_list": instrument.symbol,
            },
            headers={"User-Agent": "CrazyGame/1.0"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return parse_eastmoney_announcements(
            response.json(),
            symbol=instrument.symbol,
        )

    def _fetch_external(self, keyword: str, provider: str, api_key: str) -> list[IntelItem]:
        if not api_key:
            return []
        if provider == "tavily":
            response = httpx.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": keyword,
                    "topic": "news",
                    "max_results": 10,
                    "search_depth": "basic",
                },
                headers={"User-Agent": "CrazyGame/1.0"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return parse_tavily_results(response.json())
        if provider == "bocha":
            response = httpx.post(
                "https://api.bocha.cn/v1/web-search",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "CrazyGame/1.0",
                },
                json={
                    "query": keyword,
                    "summary": True,
                    "count": 10,
                    "freshness": "oneWeek",
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return parse_bocha_results(response.json())
        return []

    def _store_cache(self, instrument_id: int, items: list[IntelItem]) -> None:
        with self.session_factory() as db:
            for item in items:
                key = (item.url or f"{item.source}:{item.title}").rstrip("/")
                row = (
                    db.query(MarketIntel)
                    .filter_by(instrument_id=instrument_id, dedupe_key=key)
                    .one_or_none()
                )
                if row is None:
                    row = MarketIntel(
                        instrument_id=instrument_id,
                        dedupe_key=key,
                        title=item.title,
                    )
                    db.add(row)
                row.instrument_id = instrument_id
                row.source = item.source
                row.summary = item.summary
                row.url = item.url
                row.published_at = (
                    item.published_at.replace(tzinfo=None)
                    if item.published_at
                    else None
                )
                row.fetched_at = utc_now()
                row.relevance_kind = item.relevance_kind
                row.relevance_score = item.relevance_score
                row.raw_json = json.dumps(item.as_dict(), ensure_ascii=False)
            db.commit()

    def _cached_items(self, instrument_id: int) -> list[IntelItem]:
        with self.session_factory() as db:
            rows = (
                db.query(MarketIntel)
                .filter(MarketIntel.instrument_id == instrument_id)
                .order_by(MarketIntel.fetched_at.desc())
                .limit(30)
                .all()
            )
            return [
                IntelItem(
                    title=row.title,
                    summary=row.summary,
                    url=row.url,
                    source=row.source,
                    published_at=row.published_at.replace(tzinfo=timezone.utc)
                    if row.published_at
                    else None,
                    relevance_kind=row.relevance_kind,
                    relevance_score=row.relevance_score,
                )
                for row in rows
            ]

    def _fresh_cached_items(
        self,
        instrument_id: int,
        *,
        ttl_minutes: int = 15,
    ) -> list[IntelItem]:
        cutoff = utc_now()
        cutoff = cutoff.replace(microsecond=0) - timedelta(minutes=ttl_minutes)
        with self.session_factory() as db:
            rows = (
                db.query(MarketIntel)
                .filter(
                    MarketIntel.instrument_id == instrument_id,
                    MarketIntel.fetched_at >= cutoff,
                )
                .order_by(MarketIntel.fetched_at.desc())
                .limit(30)
                .all()
            )
            return [
                IntelItem(
                    title=row.title,
                    summary=row.summary,
                    url=row.url,
                    source=row.source,
                    published_at=row.published_at.replace(tzinfo=timezone.utc)
                    if row.published_at
                    else None,
                    relevance_kind=row.relevance_kind,
                    relevance_score=row.relevance_score,
                )
                for row in rows
            ]

    def fetch_for_instrument(self, instrument, *, concepts: list[str] | None = None) -> dict:
        limitations: list[str] = []
        provider_config = self._provider_config()
        tags = {"industry": "", "concepts": list(concepts or [])}
        fresh_cached = self._fresh_cached_items(instrument.id)
        if fresh_cached:
            try:
                tags = self._fetch_tags(instrument)
            except Exception:
                limitations.append("industry_tags_unavailable")
            return {
                "items": fresh_cached,
                "industry": tags.get("industry", ""),
                "concepts": tags.get("concepts", []),
                "limitations": limitations,
                "cache_state": "fresh",
            }
        raw_items: list[IntelItem] = []
        try:
            tags = self._fetch_tags(instrument)
        except Exception:
            limitations.append("industry_tags_unavailable")
        try:
            raw_items.extend(self._search_news(instrument.name))
        except Exception:
            limitations.append("news_unavailable")
        provider = str(provider_config.get("provider") or "eastmoney")
        if provider != "eastmoney":
            try:
                external = self._fetch_external(
                    f"{instrument.name} {instrument.symbol}",
                    provider,
                    str(provider_config.get("api_key") or ""),
                )
                raw_items.extend(external)
                if not external:
                    limitations.append(f"{provider}_unavailable")
            except Exception:
                limitations.append(f"{provider}_unavailable")
        try:
            raw_items.extend(self._fetch_announcements(instrument))
        except Exception:
            limitations.append("announcements_unavailable")

        if not raw_items:
            raw_items = self._cached_items(instrument.id)
            if raw_items:
                limitations.append("using_stale_news_cache")

        ranked = rank_intel_items(
            raw_items,
            symbol=instrument.symbol,
            name=instrument.name,
            industry=tags.get("industry", ""),
            concepts=tags.get("concepts", []),
            limit=8,
        )
        if ranked:
            try:
                self._store_cache(instrument.id, ranked)
            except Exception:
                limitations.append("news_cache_write_failed")
        return {
            "items": ranked,
            "industry": tags.get("industry", ""),
            "concepts": tags.get("concepts", []),
            "limitations": limitations,
            "cache_state": "live" if raw_items else "empty",
        }
