"""Headshot URL construction. `nba_person_id` is resolved once at batch-build
time in scripts/build_cache.py (see CacheRepository.players) -- the running
app never calls nba_api/CDN discovery logic, only formats a URL string.
"""
import pandas as pd

HEADSHOT_BASE_URL = "https://cdn.nba.com/headshots/nba/latest/1040x760"


def headshot_url(nba_person_id) -> str | None:
    if pd.isna(nba_person_id):
        return None
    return f"{HEADSHOT_BASE_URL}/{int(nba_person_id)}.png"
