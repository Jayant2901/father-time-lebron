"""Shared season-range constants and helpers for the acquisition scripts."""

# nba_api's advanced/per-100-possession stats are reliable from 1996-97
# onward (config.py's MetricSpec.earliest_season for nba_api-sourced metrics
# agrees).
NBA_API_START_YEAR = 1996

# Basketball-Reference's league leaderboard tables go back to the BAA's
# inaugural 1946-47 season (the league that became the NBA in 1949).
BREF_START_YEAR = 1946

# Last season assumed fully complete at the time this project was built.
# Bump this and re-run the fetch scripts once a newer season has finished --
# acquisition is a batch script, not something the running app depends on.
NBA_API_END_YEAR = 2024
BREF_END_YEAR = 2024


def season_str(start_year: int) -> str:
    """1996 -> '1996-97'."""
    return f"{start_year}-{str(start_year + 1)[-2:]}"
