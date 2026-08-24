from ecos_mcp.services import calculate, pearson


def test_descriptive_statistics():
    assert calculate([1, 2, 3], "mean") == 2
    assert calculate([1, 2, 3], "max") == 3


def test_pearson():
    assert pearson([1, 2, 3], [2, 4, 6]) == 1
