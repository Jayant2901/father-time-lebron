import pandas as pd
import pytest


@pytest.fixture
def synthetic_df() -> pd.DataFrame:
    """A small, hand-computable player-season dataset.

    4 players, 2 seasons each, ages overlapping by one year between
    consecutive players so every age from 20-24 has 1-2 data points:

        player  season  age  VAL
        P1      2000    20   10
        P1      2001    21   15
        P2      2000    21   20
        P2      2001    22   25
        P3      2000    22   30
        P3      2001    23   35
        P4      2000    23   40
        P4      2001    24   45

    Within each season, VAL is strictly increasing across players, so
    within-season percentile ranks are deterministic: 25/50/75/100.
    """
    rows = [
        ("P1", "2000", 20, 10),
        ("P1", "2001", 21, 15),
        ("P2", "2000", 21, 20),
        ("P2", "2001", 22, 25),
        ("P3", "2000", 22, 30),
        ("P3", "2001", 23, 35),
        ("P4", "2000", 23, 40),
        ("P4", "2001", 24, 45),
    ]
    df = pd.DataFrame(rows, columns=["player_id", "season", "age", "VAL"])
    df["minutes"] = 1000.0
    df["games_played"] = 50
    return df
