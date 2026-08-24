from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class Observation(BaseModel):
    date: str
    value: float | None


class IndicatorRef(BaseModel):
    id: str
    name: str
    statistic_table: str | None = None
    item: str | None = None
    statistic_name: str | None = None
    item_name: str | None = None


class SeriesMetadata(BaseModel):
    source: str = "한국은행 ECOS"
    source_name: str = "Bank of Korea ECOS Open API"
    source_api: str = "ECOS Open API"
    statistic_id: str | None = None
    statistic_name: str | None = None
    item_id: str | None = None
    item_name: str | None = None
    unit: str | None = None
    frequency: str | None = None
    seasonal_adjustment: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    retrieved_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_updated: str | None = None
    transformation: dict[str, Any] | None = None


class TimeSeries(BaseModel):
    indicator: IndicatorRef
    metadata: SeriesMetadata
    period: list[Observation]


class SearchMatch(BaseModel):
    statistic_id: str
    statistic_name: str
    item_id: str | None = None
    item_name: str | None = None
    frequency: str | None = None
    unit: str | None = None
    relevance_score: float
    reason: str
