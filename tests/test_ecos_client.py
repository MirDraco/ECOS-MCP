import httpx
import pytest

from ecos_mcp.client import EcosClient


@pytest.mark.asyncio
async def test_client_uses_ecos_path():
    def handler(request):
        assert "/StatisticSearch/demo/json/kr/1/100/T/" in str(request.url)
        return httpx.Response(200, json={"StatisticSearch": {"row": []}})

    client = EcosClient("demo", "https://example.test", transport=httpx.MockTransport(handler))
    payload = await client.statistic_search("T", "M", "2020-01", "2020-02")
    assert "StatisticSearch" in payload
