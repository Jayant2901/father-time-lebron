from fastapi import APIRouter, HTTPException

from app.core.cache_repository import get_repository
from app.schemas.models import PlayerSummary

router = APIRouter()


def _to_summary(row) -> PlayerSummary:
    return PlayerSummary(
        player_id=row["player_id"],
        display_name=row["display_name"],
        first_season=row["first_season"],
        last_season=row["last_season"],
        season_count=int(row["season_count"]),
    )


@router.get("/players", response_model=list[PlayerSummary])
def search_players(search: str = "", limit: int = 20):
    repo = get_repository()
    df = repo.search_players(search, limit=limit)
    return [_to_summary(row) for _, row in df.iterrows()]


@router.get("/players/{player_id}", response_model=PlayerSummary)
def get_player(player_id: str):
    repo = get_repository()
    row = repo.get_player(player_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown player_id '{player_id}'")
    return _to_summary(row)
