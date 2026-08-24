import asyncio
from typing import Any

import httpx

from .errors import EcosError


class EcosClient:
    def __init__(self, api_key: str | None, base_url: str, timeout: float = 20, max_retries: int = 2, transport: httpx.AsyncBaseTransport | None = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.transport = transport

    async def _get(self, endpoint: str, path: str = "") -> dict[str, Any]:
        if not self.api_key:
            raise EcosError("AUTH_REQUIRED", "ECOS_API_KEY가 설정되지 않았습니다.")
        suffix = f"/{path.lstrip('/')}" if path else ""
        url = f"{self.base_url}/{endpoint}/{self.api_key}/json/kr/1/100{suffix}"
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout, transport=self.transport) as client:
                    response = await client.get(url)
                if response.status_code in (401, 403):
                    raise EcosError("AUTH_FAILED", "ECOS API 인증에 실패했습니다.")
                if response.status_code == 429:
                    raise EcosError("RATE_LIMITED", "ECOS API 호출 한도를 초과했습니다.")
                if response.status_code >= 500 and attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                response.raise_for_status()
                payload = response.json()
                self._check_ecos_error(payload)
                return payload
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    await asyncio.sleep(2**attempt)
                    continue
                raise EcosError("TIMEOUT", "ECOS API 응답 시간이 초과되었습니다.") from exc
            except httpx.HTTPError as exc:
                raise EcosError("UPSTREAM_ERROR", "ECOS API 서버 오류가 발생했습니다.", {"status": getattr(exc.response, "status_code", None)}) from exc
        raise EcosError("UPSTREAM_ERROR", "ECOS API 요청에 실패했습니다.")

    @staticmethod
    def _check_ecos_error(payload: dict[str, Any]) -> None:
        result = payload.get("RESULT") or payload.get("result")
        if isinstance(result, dict) and str(result.get("CODE", "000")).upper() not in {"000", "SUCCESS"}:
            raise EcosError("ECOS_ERROR", str(result.get("MESSAGE", "ECOS API 오류")), result)

    async def statistic_tables(self) -> dict[str, Any]:
        return await self._get("StatisticTableList")

    async def statistic_items(self, statistic_id: str) -> dict[str, Any]:
        return await self._get("StatisticItemList", statistic_id)

    async def statistic_search(self, statistic_id: str, frequency: str, start: str, end: str, item: str = "") -> dict[str, Any]:
        return await self._get("StatisticSearch", f"{statistic_id}/{frequency}/{start}/{end}/{item}")
