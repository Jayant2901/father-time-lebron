import numpy as np
import pandas as pd

from app.analysis.percentile import add_qualified_flag, within_season_percentile


def test_qualified_flag_thresholds(synthetic_df):
    df = add_qualified_flag(synthetic_df, min_minutes=800, min_games=40)
    assert df["qualified"].all()

    df2 = synthetic_df.copy()
    df2.loc[df2["player_id"] == "P1", "minutes"] = 100
    flagged = add_qualified_flag(df2, min_minutes=800, min_games=40)
    assert not flagged.loc[flagged["player_id"] == "P1", "qualified"].any()
    assert flagged.loc[flagged["player_id"] != "P1", "qualified"].all()


def test_within_season_percentile_higher_is_better(synthetic_df):
    df = add_qualified_flag(synthetic_df, min_minutes=800, min_games=40)
    pct = within_season_percentile(df, "VAL", higher_is_better=True)
    expected = {
        ("P1", "2000"): 25.0,
        ("P2", "2000"): 50.0,
        ("P3", "2000"): 75.0,
        ("P4", "2000"): 100.0,
        ("P1", "2001"): 25.0,
        ("P2", "2001"): 50.0,
        ("P3", "2001"): 75.0,
        ("P4", "2001"): 100.0,
    }
    for idx, row in df.iterrows():
        key = (row["player_id"], row["season"])
        assert pct.loc[idx] == expected[key]


def test_within_season_percentile_lower_is_better_reverses_ranking(synthetic_df):
    df = add_qualified_flag(synthetic_df, min_minutes=800, min_games=40)
    pct_hib = within_season_percentile(df, "VAL", higher_is_better=True)
    pct_lib = within_season_percentile(df, "VAL", higher_is_better=False)
    # Ranking direction should be mirrored: hib + lib percentiles sum to 100
    # for every row (since there are no ties in this fixture).
    combined = pct_hib + pct_lib
    assert np.allclose(combined.dropna(), 100.0)


def test_unqualified_rows_are_nan(synthetic_df):
    df = synthetic_df.copy()
    df.loc[df["player_id"] == "P1", "minutes"] = 100
    df = add_qualified_flag(df, min_minutes=800, min_games=40)
    pct = within_season_percentile(df, "VAL", higher_is_better=True)
    assert pct.loc[df["player_id"] == "P1"].isna().all()


def test_season_with_fewer_than_two_qualified_rows_is_nan():
    df = pd.DataFrame(
        {
            "player_id": ["A", "B"],
            "season": ["2000", "2001"],
            "age": [20, 21],
            "VAL": [10, 20],
            "minutes": [1000.0, 1000.0],
            "games_played": [50, 50],
        }
    )
    df = add_qualified_flag(df, min_minutes=800, min_games=40)
    pct = within_season_percentile(df, "VAL", higher_is_better=True)
    assert pct.isna().all()
