import dataclasses

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.analysis.aging_curve import compute_age_baseline
from app.analysis.anomaly import compute_player_trajectory
from app.analysis.percentile import add_qualified_flag, within_season_percentile
from app.core.cache_repository import get_repository
from app.core.config import (
    LOW_CONFIDENCE_COHORT_N,
    MIN_GAMES_PER_SEASON,
    MIN_MINUTES_PER_SEASON,
    MIN_QUALIFYING_SEASONS_FOR_COHORT,
    METRICS,
    MetricSpec,
)
from app.schemas.models import (
    AgingCurveMetricResult,
    AgingCurveResponse,
    BaselinePoint,
    BaselineResponse,
    CareerSummaryOut,
    PlayerSummary,
    TrajectoryPointOut,
)

router = APIRouter()


def _prepare(df: pd.DataFrame, metric: str, spec: MetricSpec, min_minutes: float, min_games: int) -> pd.DataFrame:
    flagged = add_qualified_flag(df, min_minutes, min_games)
    flagged = flagged.copy()
    flagged["pct"] = within_season_percentile(flagged, metric, higher_is_better=spec.higher_is_better)
    return flagged


def _validate_metrics(keys: list[str]) -> None:
    unknown = [m for m in keys if m not in METRICS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown metric(s): {unknown}")


@router.get("/players/{player_id}/aging-curve", response_model=AgingCurveResponse)
def get_aging_curve(
    player_id: str,
    metrics: str = Query(..., description="Comma-separated metric keys, e.g. PTS,TS_PCT,PER"),
    min_minutes: float = MIN_MINUTES_PER_SEASON,
    min_games: int = MIN_GAMES_PER_SEASON,
    min_seasons: int = MIN_QUALIFYING_SEASONS_FOR_COHORT,
    low_confidence_n: int = LOW_CONFIDENCE_COHORT_N,
):
    repo = get_repository()
    player = repo.get_player(player_id)
    if player is None:
        raise HTTPException(status_code=404, detail=f"Unknown player_id '{player_id}'")

    requested = [m.strip() for m in metrics.split(",") if m.strip()]
    _validate_metrics(requested)

    results = []
    for metric in requested:
        spec = METRICS[metric]
        df = _prepare(repo.player_seasons, metric, spec, min_minutes, min_games)
        baseline = compute_age_baseline(df, "pct", min_seasons=min_seasons, low_confidence_n=low_confidence_n)
        points, summary = compute_player_trajectory(df, baseline, player_id, metric, "pct")

        results.append(
            AgingCurveMetricResult(
                metric=metric,
                display_name=spec.display_name,
                unit=spec.unit,
                points=[TrajectoryPointOut(**dataclasses.asdict(p)) for p in points],
                summary=CareerSummaryOut(**dataclasses.asdict(summary)),
            )
        )

    return AgingCurveResponse(
        player=PlayerSummary(
            player_id=player["player_id"],
            display_name=player["display_name"],
            first_season=player["first_season"],
            last_season=player["last_season"],
            season_count=int(player["season_count"]),
        ),
        results=results,
    )


@router.get("/baseline", response_model=BaselineResponse)
def get_baseline(
    metric: str,
    min_minutes: float = MIN_MINUTES_PER_SEASON,
    min_games: int = MIN_GAMES_PER_SEASON,
    min_seasons: int = MIN_QUALIFYING_SEASONS_FOR_COHORT,
    low_confidence_n: int = LOW_CONFIDENCE_COHORT_N,
):
    _validate_metrics([metric])
    spec = METRICS[metric]
    repo = get_repository()
    df = _prepare(repo.player_seasons, metric, spec, min_minutes, min_games)
    baseline = compute_age_baseline(df, "pct", min_seasons=min_seasons, low_confidence_n=low_confidence_n)

    points = [
        BaselinePoint(
            age=int(age),
            mean=float(row["mean"]),
            std=float(row["std"]),
            n=int(row["n"]),
            low_confidence=bool(row["low_confidence"]),
        )
        for age, row in baseline.iterrows()
    ]
    return BaselineResponse(
        metric=metric,
        display_name=spec.display_name,
        unit=spec.unit,
        min_minutes=min_minutes,
        min_games=min_games,
        min_seasons=min_seasons,
        points=points,
    )
