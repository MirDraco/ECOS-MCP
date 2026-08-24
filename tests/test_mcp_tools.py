from ecos_mcp import server


def test_required_tools_are_registered_functions():
    required = {
        "search_statistics",
        "get_statistics",
        "get_latest_value",
        "compare_statistics",
        "calculate_change",
        "calculate_spread",
        "calculate_correlation",
        "calculate_statistics",
        "get_economic_snapshot",
    }
    assert required.issubset(vars(server))
    assert all(callable(getattr(server, name)) for name in required)
