import sqlite3

import pandas as pd
import pytest

import app.core.cache_repository as cache_repository


@pytest.fixture
def synthetic_df() -> pd.DataFrame:
    """A small, hand-computable player-season dataset.

    4 players, 2 seasons each, ages overlapping by one year between
    consecutive players so every age from 20-24 has 1-2 data points:

        player  season  age  VAL
        P1      2000    20   10
        P1      2001    21   15
        P2      2000    21   20
        P2      2001    22   25
        P3      2000    22   30
        P3      2001    23   35
        P4      2000    23   40
        P4      2001    24   45

    Within each season, VAL is strictly increasing across players, so
    within-season percentile ranks are deterministic: 25/50/75/100.
    """
    rows = [
        ("P1", "2000", 20, 10),
        ("P1", "2001", 21, 15),
        ("P2", "2000", 21, 20),
        ("P2", "2001", 22, 25),
        ("P3", "2000", 22, 30),
        ("P3", "2001", 23, 35),
        ("P4", "2000", 23, 40),
        ("P4", "2001", 24, 45),
    ]
    df = pd.DataFrame(rows, columns=["player_id", "season", "age", "VAL"])
    df["minutes"] = 1000.0
    df["games_played"] = 50
    return df


METRIC_COLS = [
    "PTS", "REB", "AST", "TS_PCT", "EFG_PCT", "USG_PCT", "AST_PCT",
    "REB_PCT", "TOV_PCT", "PIE", "PER", "WS", "BPM", "VORP",
]


def _fixture_player_seasons() -> pd.DataFrame:
    # Same shape as synthetic_df above, but using the real schema/column
    # names the API expects, with PTS as the only populated metric
    # (everything else legitimately NaN, like a real player-season missing
    # a source).
    rows = [
        ("p1", "Test Player One", "2000", 20, 10.0),
        ("p1", "Test Player One", "2001", 21, 15.0),
        ("p2", "Test Player Two", "2000", 21, 20.0),
        ("p2", "Test Player Two", "2001", 22, 25.0),
        ("p3", "Test Player Three", "2000", 22, 30.0),
        ("p3", "Test Player Three", "2001", 23, 35.0),
        ("p4", "Test Player Four", "2000", 23, 40.0),
        ("p4", "Test Player Four", "2001", 24, 45.0),
    ]
    df = pd.DataFrame(rows, columns=["player_id", "player_name", "season", "age", "PTS"])
    df["games_played"] = 50
    df["minutes"] = 1000.0
    for col in METRIC_COLS:
        if col != "PTS":
            df[col] = pd.NA
    df["source_nba_api"] = True
    df["source_bref"] = False
    return df


def _fixture_players(player_seasons: pd.DataFrame) -> pd.DataFrame:
    grouped = player_seasons.groupby("player_id").agg(
        display_name=("player_name", "first"),
        first_season=("season", "min"),
        last_season=("season", "max"),
        season_count=("season", "count"),
    )
    players = grouped.reset_index()
    # Mix of resolved/unresolved nba_person_id to exercise both headshot paths.
    person_ids = {"p1": 1, "p2": None, "p3": None, "p4": None}
    players["nba_person_id"] = players["player_id"].map(person_ids)
    return players


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    player_seasons = _fixture_player_seasons()
    players = _fixture_players(player_seasons)

    with sqlite3.connect(db_path) as conn:
        player_seasons.to_sql("player_seasons", conn, index=False)
        players.to_sql("players", conn, index=False)

    monkeypatch.setattr(cache_repository, "DB_PATH", db_path)
    cache_repository.get_repository.cache_clear()

    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    cache_repository.get_repository.cache_clear()
