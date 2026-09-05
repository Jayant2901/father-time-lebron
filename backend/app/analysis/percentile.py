"""Within-season percentile ranking -- the era-normalization step.

Raw counting/rate stats drift across decades (pace, 3pt rate, rule changes),
so instead of comparing raw values across eras directly, every player-season
is first converted to a percentile rank (0-100) among the OTHER QUALIFYING
players that same season. This is the same idea as baseball's OPS+/ERA+: it
neutralizes league-average drift without needing a separate pace model per
stat. Age-based aggregation happens afterward, on these percentiles.
"""
import pandas as pd


def add_qualified_flag(
    df: pd.DataFrame,
    min_minutes: float,
    min_games: int,
    minutes_col: str = "minutes",
    games_col: str = "games_played",
) -> pd.DataFrame:
    """Mark each player-season row as qualifying (enough playing time to count)."""
    out = df.copy()
    out["qualified"] = (out[minutes_col] >= min_minutes) & (out[games_col] >= min_games)
    return out


def within_season_percentile(
    df: pd.DataFrame,
    metric: str,
    higher_is_better: bool = True,
    season_col: str = "season",
    qualified_col: str = "qualified",
) -> pd.Series:
    """Percentile rank (0-100) of each row's metric value among QUALIFYING
    player-seasons in the same season. Non-qualifying rows, and rows with a
    missing metric value (e.g. stat not tracked yet in that era), are NaN.

    A season with fewer than 2 qualifying rows for this metric produces NaN
    percentiles for that season (a rank among <2 points isn't meaningful).
    """
    masked = df[metric].where(df[qualified_col])

    def _rank_group(s: pd.Series) -> pd.Series:
        if s.notna().sum() < 2:
            return pd.Series(float("nan"), index=s.index)
        pct = s.rank(pct=True, ascending=True) * 100
        return pct if higher_is_better else 100 - pct

    return masked.groupby(df[season_col], group_keys=False).apply(_rank_group)
