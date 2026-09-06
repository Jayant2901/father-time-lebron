"""Deterministic, template-based roast text for a player's career anomaly
index. No randomness, no ML -- given the same inputs this always produces
the same output, same philosophy as the rest of /analysis.
"""

ROAST_TIERS = (
    (2.0, "{name} isn't just beating the {metric} aging curve, he's making Father Time file a complaint."),
    (1.0, "{name} has spent his whole career politely ignoring what {metric} says players his age are supposed to do."),
    (0.3, "{name} is quietly a bit better than his age-cohort at {metric} — no headlines, just steady overperformance."),
    (-0.3, "{name} ages in {metric} exactly like the history books say he should. Refreshingly normal."),
    (-1.0, "{name} is fading a little faster than his age-cohort in {metric} — Father Time's finally caught up."),
)
ROAST_FLOOR_TEMPLATE = "{name} has fully lost the {metric} argument with Father Time."


def generate_roast(career_anomaly_index: float | None, display_name: str, metric_display_name: str) -> str | None:
    """One roast line for `display_name`'s career_anomaly_index on
    `metric_display_name`. None when there's no index to roast (no
    qualifying seasons scored against the baseline).
    """
    if career_anomaly_index is None:
        return None

    for threshold, template in ROAST_TIERS:
        if career_anomaly_index >= threshold:
            return template.format(name=display_name, metric=metric_display_name)
    return ROAST_FLOOR_TEMPLATE.format(name=display_name, metric=metric_display_name)
