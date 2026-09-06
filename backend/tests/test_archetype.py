from app.analysis.anomaly import CareerSummary, TrajectoryPoint
from app.analysis.archetype import classify_archetype


def _point(age, z, low_confidence=False):
    return TrajectoryPoint(
        age=age,
        season=str(1990 + age),
        value=0.0,
        percentile=50.0,
        cohort_mean=0.0,
        cohort_std=1.0,
        cohort_n=20,
        z_score=z,
        low_confidence=low_confidence,
    )


def _summary(career_anomaly_index, qualifying_season_count, peak_anomaly_age=None):
    return CareerSummary(
        career_anomaly_index=career_anomaly_index,
        peak_anomaly_age=peak_anomaly_age,
        top_5_pct_season_count=0,
        qualifying_season_count=qualifying_season_count,
    )


def test_fewer_than_three_high_confidence_points_returns_none():
    points = [_point(20, 0.1), _point(21, 0.2, low_confidence=True)]
    summary = _summary(0.15, 2)
    assert classify_archetype(points, summary) is None


def test_flat_trajectory_is_textbook_aging_curve():
    zs = [0.05, -0.05, 0.1, -0.1, 0.0]
    points = [_point(20 + i, z) for i, z in enumerate(zs)]
    summary = _summary(sum(zs) / len(zs), len(zs), peak_anomaly_age=22)
    archetype = classify_archetype(points, summary)
    assert archetype is not None
    assert archetype.label == "Textbook Aging Curve"


def test_rising_second_half_is_late_bloomer():
    zs = [-0.5, -0.4, -0.3, 0.6, 0.8, 1.0]
    points = [_point(20 + i, z) for i, z in enumerate(zs)]
    summary = _summary(sum(zs) / len(zs), len(zs), peak_anomaly_age=25)
    archetype = classify_archetype(points, summary)
    assert archetype is not None
    assert archetype.label == "Late Bloomer"


def test_low_spread_consistently_positive_is_remarkably_consistent():
    zs = [0.5, 0.55, 0.5, 0.45, 0.5]
    points = [_point(20 + i, z) for i, z in enumerate(zs)]
    summary = _summary(sum(zs) / len(zs), len(zs), peak_anomaly_age=21)
    archetype = classify_archetype(points, summary)
    assert archetype is not None
    assert archetype.label == "Remarkably Consistent"


def test_long_career_with_late_decline_is_not_flash_in_the_pan():
    # A 15-season career that peaked early and stayed well above the
    # baseline for a decade before declining at the very end (Vince
    # Carter's real shape) must not read as "Flash in the Pan" -- that
    # label's own tagline ("it didn't last") would contradict a career
    # this long. It should fall through to "Early Peak, Fast Decline".
    zs = [1.6, 1.5, 1.4, 1.3, 1.4, 1.3, 1.2, 1.1, 1.0, 0.9, 0.5, -0.2, -0.5, -0.8, -1.0]
    points = [_point(20 + i, z) for i, z in enumerate(zs)]
    summary = _summary(sum(zs) / len(zs), len(zs), peak_anomaly_age=20)
    archetype = classify_archetype(points, summary)
    assert archetype is not None
    assert archetype.label != "Flash in the Pan"
    assert archetype.label == "Early Peak, Fast Decline"
