from ecos_mcp.cache import Cache


def test_cache_round_trip(tmp_path):
    cache = Cache(str(tmp_path / "cache.sqlite3"))
    key = cache.key({"endpoint": "test", "id": "x"})
    cache.set(key, {"value": 1}, 60)
    assert cache.get(key) == {"value": 1}
