import sqlite3

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import app.core.cache_repository as cache_repository

METRIC_COLS = [
    "PTS", "REB", "AST", "TS_PCT", "EFG_PCT", "USG_PCT", "AST_PCT",
    "REB_PCT", "TOV_PCT", "PIE", "PER", "WS", "BPM", "VORP",
]


def _fixture_player_seasons() -> pd.DataFrame:
    # Same shape as backend/tests/conftest.py's synthetic_df, but using the
    # real schema/column names the API expects, with PTS as the only
    # populated metric (everything else legitimately NaN, like a real
    # player-season missing a source).
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
    return grouped.reset_index()


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

    with TestClient(app) as test_client:
        yield test_client

    cache_repository.get_repository.cache_clear()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_search_players(client):
    resp = client.get("/players", params={"search": "player one"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["player_id"] == "p1"


def test_get_player_not_found(client):
    resp = client.get("/players/does-not-exist")
    assert resp.status_code == 404


def test_metrics_lists_pts(client):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    keys = [m["key"] for m in resp.json()]
    assert "PTS" in keys


def test_aging_curve_unknown_player(client):
    resp = client.get("/players/nobody/aging-curve", params={"metrics": "PTS"})
    assert resp.status_code == 404


def test_aging_curve_unknown_metric(client):
    resp = client.get("/players/p1/aging-curve", params={"metrics": "NOT_A_METRIC"})
    assert resp.status_code == 400


def test_aging_curve_p2_matches_hand_computed_z_scores(client):
    resp = client.get(
        "/players/p2/aging-curve",
        params={"metrics": "PTS", "min_seasons": 2, "low_confidence_n": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    result = body["results"][0]
    points = result["points"]

    assert [p["age"] for p in points] == [21, 22]
    assert points[0]["z_score"] == pytest.approx(1.0)
    assert points[1]["z_score"] == pytest.approx(-1.0)
    assert result["summary"]["peak_anomaly_age"] == 21


def test_baseline_endpoint(client):
    resp = client.get("/baseline", params={"metric": "PTS", "min_seasons": 2, "low_confidence_n": 2})
    assert resp.status_code == 200
    body = resp.json()
    ages = {p["age"]: p for p in body["points"]}
    assert ages[21]["mean"] == pytest.approx(37.5)
    assert ages[21]["n"] == 2
