import pytest


def test_compare_two_players(client):
    resp = client.get(
        "/compare",
        params={"player_ids": "p1,p2", "metric": "PTS", "min_seasons": 2, "low_confidence_n": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metric"] == "PTS"

    players = body["players"]
    assert [p["player_id"] for p in players] == ["p1", "p2"]  # order preserved

    p1, p2 = players
    assert p1["headshot_url"] == "https://cdn.nba.com/headshots/nba/latest/1040x760/1.png"
    assert p2["headshot_url"] is None

    assert p1["qualifying_season_count"] == 2
    assert p1["avg_percentile"] == pytest.approx(25.0)
    assert p1["career_anomaly_index"] == pytest.approx(-1.0)

    assert p2["qualifying_season_count"] == 2
    assert p2["avg_percentile"] == pytest.approx(50.0)
    assert p2["career_anomaly_index"] == pytest.approx(0.0)


def test_compare_verdict_names_the_better_ager(client):
    resp = client.get(
        "/compare",
        params={"player_ids": "p1,p2", "metric": "PTS", "min_seasons": 2, "low_confidence_n": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    # career_anomaly_index: p1 = -1.0, p2 = 0.0 -- a 1.0 SD gap, well above the
    # 0.15 "wash" threshold, so the verdict should name p2 as the better ager.
    assert body["verdict"] is not None
    assert "Test Player Two" in body["verdict"]
    assert "wash" not in body["verdict"]


def test_compare_single_player(client):
    resp = client.get(
        "/compare",
        params={"player_ids": "p1", "metric": "PTS", "min_seasons": 2, "low_confidence_n": 2},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["players"]) == 1
    assert body["verdict"] is None


def test_compare_unknown_player_id(client):
    resp = client.get("/compare", params={"player_ids": "p1,nobody", "metric": "PTS"})
    assert resp.status_code == 404
    assert "nobody" in resp.json()["detail"]


def test_compare_unknown_metric(client):
    resp = client.get("/compare", params={"player_ids": "p1", "metric": "NOT_A_METRIC"})
    assert resp.status_code == 400
