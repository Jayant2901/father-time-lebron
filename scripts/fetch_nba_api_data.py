"""Phase A1: pull whole-league, per-season stats from stats.nba.com via nba_api.

Calls LeagueDashPlayerStats ONCE PER SEASON per (measure_type, per_mode)
combo -- not per player -- which covers every player's entire season in one
request. Three combos per season give us everything the modern-era analysis
needs:

  Base / Totals              -> GP, MIN (total minutes) for qualifying checks
  Base / Per100Possessions   -> PTS, REB, AST etc., pace-normalized
  Advanced / PerGame         -> TS%, EFG%, USG%, AST%, REB%, TOV%, PIE
                                 (rate stats -- per_mode doesn't change them)

Raw responses are cached to data/raw/nba_api/ as CSV, one file per
(season, measure_type, per_mode). Re-running the script skips any file
that's already on disk, so it's safe to resume after a failure.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _seasons import NBA_API_END_YEAR, NBA_API_START_YEAR, season_str  # noqa: E402

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "nba_api"
REQUEST_TIMEOUT = 60
SLEEP_BETWEEN_CALLS = 1.5

COMBOS = [
    ("Base", "Totals"),
    ("Base", "Per100Possessions"),
    ("Advanced", "PerGame"),
]


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=2, max=20))
def _fetch(season: str, measure_type: str, per_mode: str) -> pd.DataFrame:
    from nba_api.stats.endpoints import leaguedashplayerstats

    resp = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        measure_type_detailed_defense=measure_type,
        per_mode_detailed=per_mode,
        timeout=REQUEST_TIMEOUT,
    )
    return resp.get_data_frames()[0]


def fetch_season(season: str) -> None:
    for measure_type, per_mode in COMBOS:
        out_path = RAW_DIR / f"{season}_{measure_type}_{per_mode}.csv"
        if out_path.exists():
            print(f"  [skip] {out_path.name} already cached")
            continue
        print(f"  [fetch] {season} {measure_type}/{per_mode} ...", end=" ", flush=True)
        try:
            df = _fetch(season, measure_type, per_mode)
        except Exception as exc:  # noqa: BLE001 -- log and keep going to the next combo
            print(f"FAILED after retries: {exc}")
            continue
        df.to_csv(out_path, index=False)
        print(f"ok ({len(df)} rows)")
        time.sleep(SLEEP_BETWEEN_CALLS)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    seasons = [season_str(y) for y in range(NBA_API_START_YEAR, NBA_API_END_YEAR + 1)]
    print(f"Fetching {len(seasons)} seasons ({seasons[0]} .. {seasons[-1]}) "
          f"x {len(COMBOS)} combos into {RAW_DIR}")
    for season in seasons:
        print(f"Season {season}:")
        fetch_season(season)
    print("Done.")


if __name__ == "__main__":
    main()
