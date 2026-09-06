import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.analysis.aging_curve import cohort_eligible_player_ids, compute_age_baseline
from app.analysis.anomaly import compute_player_trajectory
from app.analysis.archetype import classify_archetype
from app.api.aging_curve import _prepare, _validate_metrics
from app.core.cache_repository import get_repository
from app.core.config import (
    LOW_CONFIDENCE_COHORT_N,
    MIN_GAMES_PER_SEASON,
    MIN_MINUTES_PER_SEASON,
    MIN_QUALIFYING_SEASONS_FOR_COHORT,
    METRICS,
)
from app.core.headshots import headshot_url
from app.schemas.models import ArchetypeOut, LeaderboardEntry, LeaderboardResponse

router = APIRouter()

DEFAULT_LEADERBOARD_LIMIT = 20
MAX_LEADERBOARD_LIMIT = 200


def _rank_all_eligible_players(
    df: pd.DataFrame,
    baseline: pd.DataFrame,
    eligible_ids: set,
    player_col: str = "player_id",
    age_col: str = "age",
    percentile_col: str = "pct",
    minutes_col: str = "minutes",
    qualified_col: str = "qualified",
) -> pd.Series:
    """Career Anomaly Index for every cohort-eligible player, in one
    vectorized pass instead of one `compute_player_trajectory` call per
    player. Ranking ~1,800 players by looping the per-player function is
    ~6s against the real database; this join-then-groupby approach does
    the same arithmetic (see `anomaly.py::_summarize`) in ~0.4s.

    Returns a Series of career_anomaly_index indexed by player_id, for
    players with at least one scored (baseline-covered) season -- players
    with none are correctly excluded, mirroring `compute_player_trajectory`
    returning a `None` career_anomaly_index for that case.
    """
    pool = df[
        df[qualified_col] & df[player_col].isin(eligible_ids) & df[percentile_col].notna()
    ]

    joined = pool.join(baseline[["mean", "std"]], on=age_col)
    valid_std = joined["std"] > 0
    z = (joined[percentile_col] - joined["mean"]) / joined["std"].where(valid_std)

    scored = pd.DataFrame({
        "player_id": joined[player_col],
        "z": z,
        "minutes": joined[minutes_col],
    }).dropna(subset=["z"])

    total_minutes = scored.groupby("player_id")["minutes"].sum()
    weighted_sum = (scored["z"] * scored["minutes"]).groupby(scored["player_id"]).sum()
    simple_mean = scored.groupby("player_id")["z"].mean()

    weighted_mean = weighted_sum / total_minutes
    return weighted_mean.where(total_minutes > 0, simple_mean)


@router.get("/leaderboard", response_model=LeaderboardResponse)
def get_leaderboard(
    metric: str = Query(...),
    direction: str = Query("top"),
    limit: int = Query(DEFAULT_LEADERBOARD_LIMIT, ge=1, le=MAX_LEADERBOARD_LIMIT),
    min_minutes: float = MIN_MINUTES_PER_SEASON,
    min_games: int = MIN_GAMES_PER_SEASON,
    min_seasons: int = MIN_QUALIFYING_SEASONS_FOR_COHORT,
    low_confidence_n: int = LOW_CONFIDENCE_COHORT_N,
):
    if direction not in ("top", "bottom"):
        raise HTTPException(status_code=400, detail="direction must be 'top' or 'bottom'")
    _validate_metrics([metric])
    spec = METRICS[metric]
    repo = get_repository()

    df = _prepare(repo.player_seasons, metric, spec, min_minutes, min_games)
    baseline = compute_age_baseline(df, "pct", min_seasons=min_seasons, low_confidence_n=low_confidence_n)
    eligible_ids = cohort_eligible_player_ids(df, min_seasons)

    ranked = _rank_all_eligible_players(df, baseline, eligible_ids)
    ranked = ranked.sort_values(ascending=(direction == "bottom")).head(limit)

    players_by_id = repo.players.set_index("player_id")
    entries = []
    for rank, player_id in enumerate(ranked.index, start=1):
        player_row = players_by_id.loc[player_id]
        points, summary = compute_player_trajectory(df, baseline, player_id, metric, "pct")
        archetype = classify_archetype(points, summary)
        entries.append(
            LeaderboardEntry(
                rank=rank,
                player_id=player_id,
                display_name=player_row["display_name"],
                headshot_url=headshot_url(player_row.get("nba_person_id")),
                qualifying_season_count=summary.qualifying_season_count,
                career_anomaly_index=summary.career_anomaly_index,
                archetype=ArchetypeOut(label=archetype.label, tagline=archetype.tagline) if archetype else None,
            )
        )

    return LeaderboardResponse(
        metric=metric,
        display_name=spec.display_name,
        unit=spec.unit,
        direction=direction,
        entries=entries,
    )
