"""Per-player anomaly trajectory: for each qualifying season, how many
standard deviations the player's within-season percentile sits above/below
the age-cohort baseline, plus career-level summary numbers.
"""
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TrajectoryPoint:
    age: int
    season: str
    value: float
    percentile: float
    cohort_mean: float | None
    cohort_std: float | None
    cohort_n: int
    z_score: float | None
    low_confidence: bool


@dataclass(frozen=True)
class CareerSummary:
    career_anomaly_index: float | None
    peak_anomaly_age: int | None
    top_5_pct_season_count: int
    qualifying_season_count: int


def compute_player_trajectory(
    df: pd.DataFrame,
    baseline: pd.DataFrame,
    player_id,
    metric: str,
    percentile_col: str,
    player_col: str = "player_id",
    season_col: str = "season",
    age_col: str = "age",
    minutes_col: str = "minutes",
    qualified_col: str = "qualified",
) -> tuple[list[TrajectoryPoint], CareerSummary]:
    """Build one player's age-by-age trajectory against a precomputed
    `baseline` (as returned by aging_curve.compute_age_baseline), and roll it
    up into a career summary.
    """
    rows = (
        df[
            (df[player_col] == player_id)
            & df[qualified_col]
            & df[percentile_col].notna()
        ]
        .sort_values(age_col)
    )

    points: list[TrajectoryPoint] = []
    for _, row in rows.iterrows():
        age = int(row[age_col])
        pct = float(row[percentile_col])

        if age in baseline.index:
            b = baseline.loc[age]
            cohort_mean = float(b["mean"])
            cohort_std = float(b["std"])
            cohort_n = int(b["n"])
            low_confidence = bool(b["low_confidence"])
            z = (pct - cohort_mean) / cohort_std if cohort_std > 0 else None
        else:
            cohort_mean = cohort_std = None
            cohort_n = 0
            low_confidence = True
            z = None

        points.append(
            TrajectoryPoint(
                age=age,
                season=row[season_col],
                value=float(row[metric]),
                percentile=pct,
                cohort_mean=cohort_mean,
                cohort_std=cohort_std,
                cohort_n=cohort_n,
                z_score=z,
                low_confidence=low_confidence,
            )
        )

    summary = _summarize(points, rows, minutes_col)
    return points, summary


def _summarize(
    points: list[TrajectoryPoint], rows: pd.DataFrame, minutes_col: str
) -> CareerSummary:
    scored = [(p, m) for p, m in zip(points, rows[minutes_col]) if p.z_score is not None]

    if not scored:
        return CareerSummary(
            career_anomaly_index=None,
            peak_anomaly_age=None,
            top_5_pct_season_count=sum(1 for p in points if p.percentile >= 95),
            qualifying_season_count=len(points),
        )

    total_minutes = sum(m for _, m in scored)
    if total_minutes > 0:
        career_index = sum(p.z_score * m for p, m in scored) / total_minutes
    else:
        career_index = sum(p.z_score for p, _ in scored) / len(scored)

    peak = max((p for p, _ in scored), key=lambda p: p.z_score)

    return CareerSummary(
        career_anomaly_index=career_index,
        peak_anomaly_age=peak.age,
        top_5_pct_season_count=sum(1 for p in points if p.percentile >= 95),
        qualifying_season_count=len(points),
    )
