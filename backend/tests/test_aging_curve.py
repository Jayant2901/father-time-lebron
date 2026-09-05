import math

from app.analysis.aging_curve import cohort_eligible_player_ids, compute_age_baseline
from app.analysis.percentile import add_qualified_flag, within_season_percentile


def _prepared(synthetic_df):
    df = add_qualified_flag(synthetic_df, min_minutes=800, min_games=40)
    df["pct"] = within_season_percentile(df, "VAL", higher_is_better=True)
    return df


def test_cohort_eligible_player_ids_respects_min_seasons(synthetic_df):
    df = _prepared(synthetic_df)
    # Every player has exactly 2 qualifying seasons in the fixture.
    assert cohort_eligible_player_ids(df, min_seasons=2) == {"P1", "P2", "P3", "P4"}
    assert cohort_eligible_player_ids(df, min_seasons=3) == set()


def test_age_baseline_mean_and_population_std(synthetic_df):
    df = _prepared(synthetic_df)
    baseline = compute_age_baseline(df, "pct", min_seasons=2, low_confidence_n=2)

    # age 20: only P1 (pct=25) -> n=1
    assert baseline.loc[20, "n"] == 1
    assert baseline.loc[20, "mean"] == 25.0
    assert baseline.loc[20, "std"] == 0.0
    assert baseline.loc[20, "low_confidence"]

    # age 21: P1@2001 (pct=25) and P2@2000 (pct=50) -> mean 37.5, pop std 12.5
    assert baseline.loc[21, "n"] == 2
    assert baseline.loc[21, "mean"] == 37.5
    assert math.isclose(baseline.loc[21, "std"], 12.5)
    assert not baseline.loc[21, "low_confidence"]

    # age 24: only P4 (pct=100) -> n=1, low confidence
    assert baseline.loc[24, "n"] == 1
    assert baseline.loc[24, "low_confidence"]


def test_age_baseline_excludes_non_cohort_players(synthetic_df):
    df = _prepared(synthetic_df)
    # With min_seasons=3, nobody in the tiny fixture qualifies for the cohort,
    # so the baseline should be built from zero rows -> no ages present.
    baseline = compute_age_baseline(df, "pct", min_seasons=3)
    assert baseline.empty
