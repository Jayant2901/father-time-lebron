import pytest


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
    # p2 only has 2 qualifying seasons -- below classify_archetype's 3-point floor.
    assert result["archetype"] is None


def test_baseline_endpoint(client):
    resp = client.get("/baseline", params={"metric": "PTS", "min_seasons": 2, "low_confidence_n": 2})
    assert resp.status_code == 200
    body = resp.json()
    ages = {p["age"]: p for p in body["points"]}
    assert ages[21]["mean"] == pytest.approx(37.5)
    assert ages[21]["n"] == 2
