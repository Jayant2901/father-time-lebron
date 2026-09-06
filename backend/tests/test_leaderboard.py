import pytest


def test_leaderboard_top_sorts_descending(client):
    resp = client.get(
        "/leaderboard",
        params={"metric": "PTS", "direction": "top", "min_seasons": 2, "low_confidence_n": 2},
    )
    assert resp.status_code == 200
    entries = resp.json()["entries"]

    assert [e["rank"] for e in entries] == list(range(1, len(entries) + 1))
    # p4 (career_anomaly_index +1.0) is the clear top; p1 (-1.0) the clear
    # bottom -- p2/p3 tie at 0.0 in between, so their relative order isn't
    # asserted here.
    assert entries[0]["player_id"] == "p4"
    assert entries[0]["career_anomaly_index"] == pytest.approx(1.0)
    assert entries[-1]["player_id"] == "p1"
    assert entries[-1]["career_anomaly_index"] == pytest.approx(-1.0)


def test_leaderboard_bottom_sorts_ascending(client):
    resp = client.get(
        "/leaderboard",
        params={"metric": "PTS", "direction": "bottom", "min_seasons": 2, "low_confidence_n": 2},
    )
    assert resp.status_code == 200
    entries = resp.json()["entries"]

    assert entries[0]["player_id"] == "p1"
    assert entries[0]["career_anomaly_index"] == pytest.approx(-1.0)
    assert entries[-1]["player_id"] == "p4"
    assert entries[-1]["career_anomaly_index"] == pytest.approx(1.0)


def test_leaderboard_limit_is_respected(client):
    resp = client.get(
        "/leaderboard",
        params={"metric": "PTS", "limit": 1, "min_seasons": 2, "low_confidence_n": 2},
    )
    assert resp.status_code == 200
    assert len(resp.json()["entries"]) == 1


def test_leaderboard_unknown_metric_400s(client):
    resp = client.get("/leaderboard", params={"metric": "NOT_A_METRIC"})
    assert resp.status_code == 400


def test_leaderboard_unknown_direction_400s(client):
    resp = client.get("/leaderboard", params={"metric": "PTS", "direction": "sideways"})
    assert resp.status_code == 400
