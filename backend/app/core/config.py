"""Tunable constants and metric metadata for the aging-curve analysis.

These thresholds are judgment calls (what counts as a "qualifying" season,
how many seasons make a player part of the baseline-building cohort, how
small a cohort has to be before we flag low confidence). They live here as
named constants instead of magic numbers, and the API exposes overrides for
the season/cohort thresholds so the choice is demonstrable, not hidden.
"""
from dataclasses import dataclass

# A player-season must clear these to count toward within-season percentiles
# and toward any age-cohort baseline at all.
MIN_MINUTES_PER_SEASON = 800
MIN_GAMES_PER_SEASON = 40

# A player must have at least this many qualifying seasons in their career to
# be included in the population used to BUILD the age-baseline (keeps
# fringe/injury-shortened careers from skewing "typical" aging curves). This
# does NOT restrict which players can be looked up/plotted against the
# baseline -- any player's qualifying seasons can be compared to it.
MIN_QUALIFYING_SEASONS_FOR_COHORT = 3

# Below this many cohort player-seasons at a given age, the baseline mean/std
# at that age is flagged low_confidence rather than presented at full
# confidence.
LOW_CONFIDENCE_COHORT_N = 15

# Age is computed as of Feb 1 of the season (matches Basketball-Reference's
# convention, so computed ages can be cross-checked against BR's own
# published age column).
AGE_REFERENCE_MONTH_DAY = (2, 1)


@dataclass(frozen=True)
class MetricSpec:
    key: str
    display_name: str
    higher_is_better: bool = True
    source: str = "nba_api"  # "nba_api" or "bref"
    earliest_season: str | None = None
    unit: str = ""


METRICS: dict[str, MetricSpec] = {
    "PTS": MetricSpec("PTS", "Points per 100 Possessions", True, "nba_api", "1996-97"),
    "REB": MetricSpec("REB", "Rebounds per 100 Possessions", True, "nba_api", "1996-97"),
    "AST": MetricSpec("AST", "Assists per 100 Possessions", True, "nba_api", "1996-97"),
    "TS_PCT": MetricSpec("TS_PCT", "True Shooting %", True, "nba_api", "1996-97", "%"),
    "EFG_PCT": MetricSpec("EFG_PCT", "Effective FG %", True, "nba_api", "1996-97", "%"),
    "USG_PCT": MetricSpec("USG_PCT", "Usage %", True, "nba_api", "1996-97", "%"),
    "AST_PCT": MetricSpec("AST_PCT", "Assist %", True, "nba_api", "1996-97", "%"),
    "TOV_PCT": MetricSpec("TOV_PCT", "Turnover %", False, "nba_api", "1996-97", "%"),
    "REB_PCT": MetricSpec("REB_PCT", "Rebound %", True, "nba_api", "1996-97", "%"),
    "PIE": MetricSpec("PIE", "Player Impact Estimate", True, "nba_api", "1996-97"),
    "PER": MetricSpec("PER", "Player Efficiency Rating", True, "bref", "1951-52"),
    "WS": MetricSpec("WS", "Win Shares", True, "bref", "1951-52"),
    "BPM": MetricSpec("BPM", "Box Plus/Minus", True, "bref", "1973-74"),
    "VORP": MetricSpec("VORP", "Value Over Replacement Player", True, "bref", "1973-74"),
}
