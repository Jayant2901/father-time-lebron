"""Population aging-curve baseline: per-age mean/std/n of within-season
percentile, pooled across all qualifying player-seasons in NBA history.
"""
from dataclasses import dataclass

import pandas as pd

from app.core.config import LOW_CONFIDENCE_COHORT_N, MIN_QUALIFYING_SEASONS_FOR_COHORT


@dataclass(frozen=True)
class AgePoint:
    age: int
    mean: float
    std: float
    n: int
    low_confidence: bool


def cohort_eligible_player_ids(
    df: pd.DataFrame,
    min_seasons: int = MIN_QUALIFYING_SEASONS_FOR_COHORT,
    player_col: str = "player_id",
    qualified_col: str = "qualified",
) -> set:
    """Players with at least `min_seasons` qualifying seasons across their
    career -- these are the players whose seasons feed the age baseline.
    (This does not restrict who can be *looked up* against the baseline.)
    """
    counts = df.loc[df[qualified_col]].groupby(player_col).size()
    return set(counts[counts >= min_seasons].index)


def compute_age_baseline(
    df: pd.DataFrame,
    percentile_col: str,
    min_seasons: int = MIN_QUALIFYING_SEASONS_FOR_COHORT,
    low_confidence_n: int = LOW_CONFIDENCE_COHORT_N,
    player_col: str = "player_id",
    age_col: str = "age",
    qualified_col: str = "qualified",
) -> pd.DataFrame:
    """Build the per-age baseline (mean/std/n of `percentile_col`) pooled over
    cohort-eligible players' qualifying seasons.

    Returns a DataFrame indexed by age with columns: mean, std, n, low_confidence.
    Uses population std (ddof=0) -- we have the full cohort population at each
    age, not a sample drawn from it, so there is no reason to apply Bessel's
    correction.
    """
    eligible_ids = cohort_eligible_player_ids(df, min_seasons, player_col, qualified_col)
    pool = df[df[qualified_col] & df[player_col].isin(eligible_ids) & df[percentile_col].notna()]

    grouped = pool.groupby(age_col)[percentile_col]
    baseline = pd.DataFrame(
        {
            "mean": grouped.mean(),
            "std": grouped.std(ddof=0),
            "n": grouped.size(),
        }
    )
    baseline["low_confidence"] = baseline["n"] < low_confidence_n
    # A cohort of size 1 has std=0 (only one value observed); that's the
    # mathematically correct population std, but downstream z-scores would
    # divide by zero -- treat it as always low-confidence and let callers
    # guard against std==0 explicitly rather than silently producing inf.
    baseline.loc[baseline["n"] <= 1, "low_confidence"] = True
    return baseline.sort_index()
