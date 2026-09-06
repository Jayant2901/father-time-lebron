from fastapi import APIRouter, HTTPException, Query

from app.analysis.aging_curve import compute_age_baseline
from app.analysis.anomaly import compute_player_trajectory
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
from app.schemas.models import ComparePlayerOut, CompareResponse

router = APIRouter()


def _generate_verdict(players: list[ComparePlayerOut], display_name: str) -> str | None:
    scored = [p for p in players if p.career_anomaly_index is not None]
    if len(scored) < 2:
        return None
    ranked = sorted(scored, key=lambda p: p.career_anomaly_index, reverse=True)
    best, worst = ranked[0], ranked[-1]
    if best.career_anomaly_index - worst.career_anomaly_index < 0.15:
        return f"Basically a wash on {display_name} — less than 0.15 SD separates them, career-wide."
    return (
        f"{best.display_name} aged better relative to his cohort in {display_name}: "
        f"{best.career_anomaly_index:+.2f} SD vs {worst.display_name}'s {worst.career_anomaly_index:+.2f} SD, career-wide."
    )


@router.get("/compare", response_model=CompareResponse)
def compare_players(
    player_ids: str = Query(..., description="Comma-separated player_id values, e.g. lebron james,michael jordan"),
    metric: str = Query(...),
    min_minutes: float = MIN_MINUTES_PER_SEASON,
    min_games: int = MIN_GAMES_PER_SEASON,
    min_seasons: int = MIN_QUALIFYING_SEASONS_FOR_COHORT,
    low_confidence_n: int = LOW_CONFIDENCE_COHORT_N,
):
    _validate_metrics([metric])
    spec = METRICS[metric]
    repo = get_repository()

    ids = [p.strip() for p in player_ids.split(",") if p.strip()]
    if not ids:
        raise HTTPException(status_code=400, detail="player_ids must contain at least one player_id")

    rows = {}
    missing = []
    for pid in ids:
        row = repo.get_player(pid)
        if row is None:
            missing.append(pid)
        else:
            rows[pid] = row
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown player_id(s): {missing}")

    df = _prepare(repo.player_seasons, metric, spec, min_minutes, min_games)
    baseline = compute_age_baseline(df, "pct", min_seasons=min_seasons, low_confidence_n=low_confidence_n)

    out = []
    for pid in ids:  # preserve caller's requested order
        row = rows[pid]
        points, summary = compute_player_trajectory(df, baseline, pid, metric, "pct")
        avg_pct = (sum(p.percentile for p in points) / len(points)) if points else None
        out.append(
            ComparePlayerOut(
                player_id=row["player_id"],
                display_name=row["display_name"],
                headshot_url=headshot_url(row.get("nba_person_id")),
                qualifying_season_count=summary.qualifying_season_count,
                avg_percentile=avg_pct,
                career_anomaly_index=summary.career_anomaly_index,
            )
        )

    return CompareResponse(
        metric=metric,
        display_name=spec.display_name,
        unit=spec.unit,
        players=out,
        verdict=_generate_verdict(out, spec.display_name),
    )
