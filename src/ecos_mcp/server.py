import asyncio
import itertools
from typing import Literal

from mcp.server.fastmcp import FastMCP

from .cache import Cache
from .client import EcosClient
from .config import get_settings
from .errors import EcosError
from .services import EcosService, align, calculate, pearson

settings = get_settings()
client = EcosClient(settings.ecos_api_key, settings.ecos_base_url, settings.ecos_timeout_seconds, settings.ecos_max_retries)
cache = Cache(settings.cache_path) if settings.cache_enabled else None
service = EcosService(client, cache, settings.cache_ttl_seconds)
mcp = FastMCP("ecos-economic-data", host=settings.mcp_host, port=settings.mcp_port)


def safe(call):
    try:
        return asyncio.run(call)
    except EcosError as error:
        return error.as_dict()


@mcp.tool()
def search_statistics(query: str, limit: int = 10) -> dict:
    """Search Bank of Korea ECOS statistic tables and items by natural language. Returns scored candidates and identifiers; ambiguous results are not auto-selected."""
    return safe(service.search(query, max(1, min(limit, 50))))


@mcp.tool()
def get_statistics(indicator: str, start_date: str, end_date: str, frequency: Literal["D", "M", "Q", "A"] = "M") -> dict:
    """Retrieve normalized historical ECOS time-series data. The indicator can be natural language; metadata includes source, unit, frequency, and dates."""
    result = safe(service.series(indicator, start_date, end_date, frequency))
    return result if isinstance(result, dict) and "success" in result else {"success": True, **result.model_dump()}


@mcp.tool()
def get_latest_value(indicator: str) -> dict:
    """Retrieve the latest available ECOS observation for a natural-language indicator, with its actual period, unit, frequency, and source metadata."""
    return safe(service.latest(indicator))


@mcp.tool()
def compare_statistics(indicators: list[str], start_date: str, end_date: str, frequency: Literal["D", "M", "Q", "A"] = "M") -> dict:
    """Fetch multiple indicators, preserve each unit, and return only periods common to all series. No cross-unit values are silently combined."""
    async def run():
        series = await asyncio.gather(*(service.series(item, start_date, end_date, frequency) for item in indicators))
        return {"success": True, "frequency": frequency, "series": [item.model_dump() for item in series], "aligned_period": align(series)}
    return safe(run())


@mcp.tool()
def calculate_change(indicator: str, start_date: str, end_date: str, calculation: Literal["absolute", "percent", "mom", "qoq", "yoy"] = "percent", frequency: Literal["D", "M", "Q", "A"] = "M") -> dict:
    """Calculate absolute or relative changes from a normalized ECOS series. yoy uses 12 periods for monthly, qoq uses 4 for quarterly, and missing observations remain missing."""
    async def run():
        series = await service.series(indicator, start_date, end_date, frequency)
        lag = {"mom": 1, "qoq": 1, "yoy": 12 if frequency == "M" else 4 if frequency == "Q" else 1}.get(calculation, 1)
        values = []
        for index, obs in enumerate(series.period):
            if index < lag: continue
            previous = series.period[index - lag].value
            change = obs.value - previous if calculation == "absolute" else ((obs.value / previous) - 1) * 100 if previous else None
            values.append({"date": obs.date, "value": change})
        return {"success": True, "indicator": series.indicator.model_dump(), "calculation": calculation, "unit": "%" if calculation != "absolute" else series.metadata.unit, "period": values, "metadata": series.metadata.model_dump()}
    return safe(run())


@mcp.tool()
def calculate_spread(left_indicator: str, right_indicator: str, operation: Literal["subtract", "add"] = "subtract", start_date: str = "2000", end_date: str = "9999", frequency: Literal["D", "M", "Q", "A"] = "M") -> dict:
    """Align two ECOS series and calculate a documented spread. Returns an explicit unit mismatch error when units differ."""
    async def run():
        left, right = await asyncio.gather(service.series(left_indicator, start_date, end_date, frequency), service.series(right_indicator, start_date, end_date, frequency))
        if left.metadata.unit and right.metadata.unit and left.metadata.unit != right.metadata.unit:
            raise EcosError("UNIT_MISMATCH", "단위가 다른 지표의 산술 결합은 지원하지 않습니다.", {"left_unit": left.metadata.unit, "right_unit": right.metadata.unit})
        rows = align([left, right])
        return {"success": True, "operation": operation, "unit": left.metadata.unit, "period": [{"period": row["date"], "left_value": row[left_indicator], "right_value": row[right_indicator], "spread": row[left_indicator] - row[right_indicator] if operation == "subtract" else row[left_indicator] + row[right_indicator]} for row in rows]}
    return safe(run())


@mcp.tool()
def calculate_correlation(indicators: list[str], start_date: str, end_date: str, method: Literal["pearson"] = "pearson", frequency: Literal["D", "M", "Q", "A"] = "M") -> dict:
    """Calculate objective Pearson correlations on common periods and report sample size; correlation does not imply causation."""
    async def run():
        series = await asyncio.gather(*(service.series(item, start_date, end_date, frequency) for item in indicators))
        rows = align(series)
        correlations = {}
        for left, right in itertools.combinations(indicators, 2):
            correlations[f"{left}|{right}"] = pearson([row[left] for row in rows], [row[right] for row in rows])
        return {"success": True, "method": method, "sample_size": len(rows), "correlations": correlations, "correlation_does_not_imply_causation": True}
    return safe(run())


@mcp.tool()
def calculate_statistics(values: list[float], operation: Literal["mean", "median", "min", "max", "standard_deviation", "variance"]) -> dict:
    """Calculate a descriptive statistic over already retrieved numeric values."""
    try:
        return {"success": True, "operation": operation, "value": calculate(values, operation), "sample_size": len(values)}
    except EcosError as error:
        return error.as_dict()


@mcp.tool()
def get_economic_snapshot(country: Literal["KR"] = "KR", date: str = "latest") -> dict:
    """Return a best-effort Korean economic snapshot from resolvable ECOS indicators; unavailable indicators are reported, never fabricated."""
    async def run():
        requested = ["한국 기준금리", "소비자물가", "GDP 성장률", "M2", "원달러 환율", "실업률", "산업생산"]
        results = await asyncio.gather(*(service.latest(item) for item in requested), return_exceptions=True)
        return {"success": True, "country": country, "date": date, "available": [item for item in results if isinstance(item, dict) and item.get("success")], "unavailable": [{"indicator": name, "reason": str(result)} for name, result in zip(requested, results) if not isinstance(result, dict) or not result.get("success")]}
    return safe(run())


def main() -> None:
    mcp.run(transport="streamable-http")
