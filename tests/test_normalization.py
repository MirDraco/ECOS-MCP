from ecos_mcp.services import _number


def test_special_numeric_values_are_missing():
    assert _number("N/A") is None
    assert _number("-") is None
    assert _number("1,234.5") == 1234.5
