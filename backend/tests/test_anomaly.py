import math

from app.analysis.aging_curve import compute_age_baseline
from app.analysis.anomaly import compute_player_trajectory
from app.analysis.percentile import add_qualified_flag, within_season_percentile


def _prepared(synthetic_df):
    df = add_qualified_flag(synthetic_df, min_minutes=800, min_games=40)
    df["pct"] = within_season_percentile(df, "VAL", higher_is_better=True)
    return df


def test_trajectory_z_scores_and_career_summary(synthetic_df):
    df = _prepared(synthetic_df)
    baseline = compute_age_baseline(df, "pct", min_seasons=2, low_confidence_n=2)

    points, summary = compute_player_trajectory(df, baseline, "P2", "VAL", "pct")

    assert [p.age for p in points] == [21, 22]
    assert math.isclose(points[0].z_score, 1.0)
    assert math.isclose(points[1].z_score, -1.0)
    assert not points[0].low_confidence
    assert not points[1].low_confidence

    # Equal minutes in both seasons -> minutes-weighted mean == simple mean == 0
    assert math.isclose(summary.career_anomaly_index, 0.0, abs_tol=1e-9)
    assert summary.peak_anomaly_age == 21
    assert summary.top_5_pct_season_count == 0
    assert summary.qualifying_season_count == 2


def test_trajectory_flags_ages_missing_from_baseline(synthetic_df):
    df = _prepared(synthetic_df)
    # Build a baseline that only covers ages 21-22 (drop 20/23/24 rows first).
    narrow_df = df[df["age"].isin([21, 22])]
    baseline = compute_age_baseline(narrow_df, "pct", min_seasons=1, low_confidence_n=2)

    points, _ = compute_player_trajectory(df, baseline, "P4", "VAL", "pct")
    # P4's qualifying ages are 23 and 24, neither present in the baseline.
    assert all(p.z_score is None for p in points)
    assert all(p.low_confidence for p in points)


def test_trajectory_empty_for_player_with_no_qualifying_seasons(synthetic_df):
    df = _prepared(synthetic_df)
    df.loc[df["player_id"] == "P3", "minutes"] = 0
    df = add_qualified_flag(df, min_minutes=800, min_games=40)
    df["pct"] = within_season_percentile(df, "VAL", higher_is_better=True)
    baseline = compute_age_baseline(df, "pct", min_seasons=1, low_confidence_n=2)

    points, summary = compute_player_trajectory(df, baseline, "P3", "VAL", "pct")
    assert points == []
    assert summary.career_anomaly_index is None
    assert summary.peak_anomaly_age is None
    assert summary.qualifying_season_count == 0
