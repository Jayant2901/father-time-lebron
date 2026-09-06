from app.analysis.roast import generate_roast


def test_none_index_returns_none():
    assert generate_roast(None, "Test Player", "Player Efficiency Rating") is None


def test_each_tier_produces_distinct_nonempty_text():
    values = [2.5, 1.5, 0.5, 0.0, -0.5, -1.5]
    lines = [generate_roast(z, "Test Player", "PER") for z in values]

    assert all(line for line in lines)
    assert len(set(lines)) == len(lines)
    for line in lines:
        assert "Test Player" in line
        assert "PER" in line


def test_tier_boundaries_are_inclusive_on_the_high_side():
    assert generate_roast(2.0, "P", "PER") == generate_roast(2.5, "P", "PER")
    assert generate_roast(1.0, "P", "PER") != generate_roast(0.99, "P", "PER")
