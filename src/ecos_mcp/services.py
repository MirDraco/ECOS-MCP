import itertools
import math
import re
from datetime import date
from statistics import mean, median, stdev, variance
from typing import Any

from .cache import Cache
from .client import EcosClient
from .errors import AmbiguousIndicatorError, EcosError
from .models import IndicatorRef, Observation, SearchMatch, SeriesMetadata, TimeSeries


def _rows(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key) or payload.get(key.lower()) or {}
    return value.get("row", []) if isinstance(value, dict) else []


def _number(value: Any) -> float | None:
    if value is None or str(value).strip().upper() in {"", "N/A", "-", "..."}:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


class EcosService:
    def __init__(self, client: EcosClient, cache: Cache | None = None, cache_ttl: int = 86400):
        self.client, self.cache, self.cache_ttl = client, cache, cache_ttl

    async def _cached(self, request: dict[str, Any], fetch):
        if self.cache:
            cached = self.cache.get(self.cache.key(request))
            if cached is not None:
                return cached
        payload = await fetch()
        if self.cache:
            self.cache.set(self.cache.key(request), payload, self.cache_ttl)
        return payload

    async def search(self, query: str, limit: int = 10) -> dict[str, Any]:
        tables = await self._cached({"endpoint": "StatisticTableList"}, self.client.statistic_tables)
        terms = [term.lower() for term in re.findall(r"[\w가-힣]+", query)]
        candidates: list[SearchMatch] = []
        for row in _rows(tables, "StatisticTableList"):
            name = str(row.get("STAT_NM") or row.get("stat_name") or row.get("STAT_NAME") or "")
            text = name.lower()
            hits = sum(term in text for term in terms)
            if hits:
                candidates.append(SearchMatch(statistic_id=str(row.get("STAT_CODE") or row.get("stat_code")), statistic_name=name, relevance_score=hits / max(len(terms), 1), reason=f"통계표명에서 {hits}개 검색어 일치"))
        candidates.sort(key=lambda item: item.relevance_score, reverse=True)
        enriched: list[SearchMatch] = []
        for candidate in candidates[:limit]:
            try:
                items = await self._cached({"endpoint": "StatisticItemList", "statistic_id": candidate.statistic_id}, lambda: self.client.statistic_items(candidate.statistic_id))
                for row in _rows(items, "StatisticItemList")[:limit]:
                    item_name = str(row.get("ITEM_NM") or row.get("item_name") or row.get("ITEM_NAME") or "")
                    item_hits = sum(term in item_name.lower() for term in terms)
                    enriched.append(candidate.model_copy(update={"item_id": str(row.get("ITEM_CODE") or row.get("item_code") or ""), "item_name": item_name, "relevance_score": candidate.relevance_score + item_hits, "reason": candidate.reason + (f"; 항목명에서 {item_hits}개 일치" if item_hits else "")}))
            except EcosError:
                enriched.append(candidate)
        enriched.sort(key=lambda item: item.relevance_score, reverse=True)
        return {"success": True, "query": query, "matches": [item.model_dump() for item in enriched[:limit]]}

    async def resolve(self, indicator: str) -> SearchMatch:
        result = await self.search(indicator, 10)
        matches = [SearchMatch.model_validate(item) for item in result["matches"]]
        if not matches:
            raise EcosError("NO_MATCH", "요청한 지표와 일치하는 ECOS 통계항목이 없습니다.", {"indicator": indicator})
        if len(matches) > 1 and matches[0].relevance_score == matches[1].relevance_score:
            raise AmbiguousIndicatorError([item.model_dump() for item in matches])
        return matches[0]

    async def series(self, indicator: str, start: str, end: str, frequency: str = "M") -> TimeSeries:
        match = await self.resolve(indicator)
        request = {"endpoint": "StatisticSearch", "statistic_id": match.statistic_id, "item_id": match.item_id, "start_date": start, "end_date": end, "frequency": frequency}
        payload = await self._cached(request, lambda: self.client.statistic_search(match.statistic_id, frequency, start, end, match.item_id or ""))
        rows = _rows(payload, "StatisticSearch")
        observations = [Observation(date=str(row.get("TIME") or row.get("time")), value=_number(row.get("DATA_VALUE") or row.get("data_value"))) for row in rows]
        observations = [item for item in observations if item.date and item.value is not None]
        if not observations:
            raise EcosError("NO_DATA", "요청한 기간에 대한 데이터가 없습니다.", {"indicator": indicator, "start_date": start, "end_date": end})
        metadata = SeriesMetadata(statistic_id=match.statistic_id, statistic_name=match.statistic_name, item_id=match.item_id, item_name=match.item_name, frequency=frequency, unit=(rows[0].get("UNIT_NAME") if rows else None), start_date=observations[0].date, end_date=observations[-1].date)
        return TimeSeries(indicator=IndicatorRef(id=f"{match.statistic_id}:{match.item_id}", name=indicator, statistic_table=match.statistic_id, item=match.item_id, statistic_name=match.statistic_name, item_name=match.item_name), metadata=metadata, period=observations)

    async def latest(self, indicator: str) -> dict[str, Any]:
        series = await self.series(indicator, "1900-01-01", date.today().isoformat(), "D")
        latest = series.period[-1]
        return {"success": True, "indicator": series.indicator.model_dump(), "value": latest.value, "unit": series.metadata.unit, "period": latest.date, "frequency": series.metadata.frequency, "source": series.metadata.source, "metadata": series.metadata.model_dump()}


def align(series: list[TimeSeries]) -> list[dict[str, Any]]:
    common = set.intersection(*(set(item.date for item in value.period) for value in series))
    return [{"date": date, **{item.indicator.name: next(obs.value for obs in item.period if obs.date == date) for item in series}} for date in sorted(common)]


def calculate(values: list[float], operation: str) -> float | None:
    if not values:
        return None
    if operation == "mean": return mean(values)
    if operation == "median": return median(values)
    if operation == "min": return min(values)
    if operation == "max": return max(values)
    if operation == "standard_deviation": return stdev(values) if len(values) > 1 else 0.0
    if operation == "variance": return variance(values) if len(values) > 1 else 0.0
    raise EcosError("INVALID_CALCULATION", f"지원하지 않는 계산입니다: {operation}")


def pearson(x: list[float], y: list[float]) -> float | None:
    if len(x) < 2 or len(x) != len(y): return None
    mx, my = mean(x), mean(y)
    dx, dy = [value - mx for value in x], [value - my for value in y]
    denominator = math.sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    return sum(a * b for a, b in zip(dx, dy)) / denominator if denominator else None
