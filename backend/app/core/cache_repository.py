"""Loads the pre-built SQLite cache (data/processed/nba_aging.db) into memory
once at startup. The app never touches nba_api or Basketball-Reference at
request time -- see scripts/build_cache.py for how the cache is produced.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from functools import lru_cache

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "processed" / "nba_aging.db"


class CacheRepository:
    def __init__(self, db_path: Path = DB_PATH):
        if not db_path.exists():
            raise FileNotFoundError(
                f"{db_path} not found -- run scripts/fetch_nba_api_data.py, "
                "scripts/fetch_basketball_reference.py, then scripts/build_cache.py first."
            )
        with sqlite3.connect(db_path) as conn:
            self.player_seasons = pd.read_sql("SELECT * FROM player_seasons", conn)
            self.players = pd.read_sql("SELECT * FROM players", conn)

    def search_players(self, query: str, limit: int = 20) -> pd.DataFrame:
        q = query.strip().lower()
        if not q:
            return self.players.sort_values("season_count", ascending=False).head(limit)
        mask = self.players["display_name"].str.lower().str.contains(q, na=False)
        return self.players[mask].sort_values("season_count", ascending=False).head(limit)

    def get_player(self, player_id: str) -> pd.Series | None:
        rows = self.players[self.players["player_id"] == player_id]
        return None if rows.empty else rows.iloc[0]

    def get_player_seasons(self, player_id: str) -> pd.DataFrame:
        return self.player_seasons[self.player_seasons["player_id"] == player_id].sort_values("age")


@lru_cache(maxsize=1)
def get_repository() -> CacheRepository:
    # DB_PATH looked up dynamically (not bound as a default arg) so tests can
    # monkeypatch the module-level constant and clear the cache to point this
    # at a temporary fixture database.
    return CacheRepository(DB_PATH)
