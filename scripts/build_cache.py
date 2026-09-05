"""Merge cached nba_api + Basketball-Reference raw pulls into the canonical
SQLite cache the FastAPI app reads (data/processed/nba_aging.db).

Player identity across the two sources is unified by a normalized NAME KEY
rather than either source's native ID, because pre-1996 seasons only exist
in Basketball-Reference (nba_api has no numeric ID to anchor to) and the app
needs one consistent player_id space spanning the full 1946-2024 history.

Name normalization deliberately keeps suffixes (Jr./Sr./II/III/IV) --
stripping them would wrongly merge distinct real people who share a
surname across generations (e.g. Larry Nance and Larry Nance Jr., both
NBA players). It only strips punctuation/accents/casing, which is enough
to reconcile formatting differences like "PJ Tucker" vs "P.J. Tucker" or
"Nikola Jokic" vs "Nikola Jokić".

Any Basketball-Reference row in a season nba_api also covers, whose name key
doesn't match an nba_api row, is kept (with nba_api-sourced metrics NaN)
rather than dropped, and logged to data/processed/unmatched_bref_rows.csv
for manual inspection.
"""
from __future__ import annotations

import re
import sqlite3
import sys
import unicodedata
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _seasons import BREF_END_YEAR, BREF_START_YEAR, NBA_API_END_YEAR, NBA_API_START_YEAR, season_str  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAW_NBA_API = ROOT / "data" / "raw" / "nba_api"
RAW_BREF = ROOT / "data" / "raw" / "bref"
DB_PATH = ROOT / "data" / "processed" / "nba_aging.db"
REPORT_PATH = ROOT / "data" / "processed" / "unmatched_bref_rows.csv"

MIN_TABLE_BYTES = 5000  # guards against caching a challenge/error page as if it were data


# ---------------------------------------------------------------- identity --

_ALIAS_OVERRIDES = {
    # Well-known cross-era name changes -- not exhaustive, just the most
    # famous cases likely to come up when exploring the tool.
    "ron artest": "metta world peace",
    "lloyd b free": "world b free",
}


_SUFFIX_RE = re.compile(r"\s+(jr|sr|ii|iii|iv|v)$")


def normalize_name_key(name: str) -> str:
    """Strict cross-source/cross-season join key: unicode/punctuation/casing
    normalized, but generational suffixes (Jr./Sr./II/III/IV) are KEPT.

    Verified empirically (see data/raw/bref/*_advanced.html) that
    Basketball-Reference itself distinguishes real father/son duos by suffix
    just like nba_api does -- e.g. both sources list "Tim Hardaway Jr." and
    "Larry Nance Jr." with the suffix, never collapsing them into the
    father's "Tim Hardaway" / "Larry Nance". So the strict key is what
    correctly keeps generational duos separate, and is used for every
    player's canonical identity across their whole career.

    A separate loose_key() (suffix stripped) is used ONLY as a same-season
    fallback match in merge_season(), for the different problem of nba_api
    using full legal names some players aren't otherwise known by (e.g.
    "Jimmy Butler III", "Johnny O'Bryant III") that Basketball-Reference
    lists without any suffix at all -- a single real person, inconsistently
    spelled, not two people.
    """
    if not isinstance(name, str):
        return ""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    name = name.lower().strip()
    name = _ALIAS_OVERRIDES.get(name, name)
    name = re.sub(r"[.'\-,]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def loose_key(strict_key: str) -> str:
    return _SUFFIX_RE.sub("", strict_key)


# ------------------------------------------------------------- nba_api load --

def load_nba_api_season(season: str) -> pd.DataFrame | None:
    totals_path = RAW_NBA_API / f"{season}_Base_Totals.csv"
    per100_path = RAW_NBA_API / f"{season}_Base_Per100Possessions.csv"
    adv_path = RAW_NBA_API / f"{season}_Advanced_PerGame.csv"
    if not (totals_path.exists() and per100_path.exists() and adv_path.exists()):
        return None

    totals = pd.read_csv(totals_path)
    per100 = pd.read_csv(per100_path)
    adv = pd.read_csv(adv_path)

    base = totals[["PLAYER_ID", "PLAYER_NAME", "AGE", "GP", "MIN"]].rename(
        columns={"AGE": "age", "GP": "games_played", "MIN": "minutes"}
    )

    per100_cols = per100[["PLAYER_ID", "PTS", "REB", "AST"]]
    adv_cols = adv[
        ["PLAYER_ID", "TS_PCT", "EFG_PCT", "USG_PCT", "AST_PCT", "REB_PCT", "TM_TOV_PCT", "PIE"]
    ].rename(columns={"TM_TOV_PCT": "TOV_PCT"})
    # nba_api reports percentages as fractions (0-1); scale to 0-100 to match
    # Basketball-Reference's convention for the same stats.
    for col in ["TS_PCT", "EFG_PCT", "USG_PCT", "AST_PCT", "REB_PCT", "TOV_PCT"]:
        adv_cols[col] = adv_cols[col] * 100

    df = base.merge(per100_cols, on="PLAYER_ID", how="left").merge(adv_cols, on="PLAYER_ID", how="left")
    df["player_id"] = df["PLAYER_NAME"].map(normalize_name_key)
    df["player_name"] = df["PLAYER_NAME"]
    df["season"] = season
    df["source_nba_api"] = True
    return df.drop(columns=["PLAYER_ID", "PLAYER_NAME"])


# --------------------------------------------------------------- bref load --

def _dedupe_multi_team(df: pd.DataFrame) -> pd.DataFrame:
    """Basketball-Reference lists one row per team stint for a traded player
    PLUS an aggregate row (Team in {2TM, 3TM, ...}) with season totals.
    Keep only the aggregate row when present; otherwise keep the single row.
    """
    df = df[df["Player"].notna() & (df["Player"] != "League Average")].copy()
    is_agg = df["Team"].astype(str).str.endswith("TM")
    has_agg = is_agg.groupby(df["Player"]).transform("any")
    return df[~has_agg | is_agg].drop(columns=[c for c in [] if c in df.columns])


def load_bref_season(season: str) -> pd.DataFrame | None:
    path = RAW_BREF / f"{season}_advanced.html"
    if not path.exists():
        return None
    html = path.read_text(encoding="utf-8")
    if len(html) < MIN_TABLE_BYTES:
        return None

    tables = pd.read_html(StringIO(html))
    raw = tables[0]
    raw = _dedupe_multi_team(raw)
    if raw.empty:
        return None

    wanted = ["Player", "Age", "G", "MP", "PER", "WS", "BPM", "VORP"]
    raw = raw.reindex(columns=wanted)
    for col in ["Age", "G", "MP", "PER", "WS", "BPM", "VORP"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    df = raw.rename(
        columns={"Age": "age", "G": "games_played", "MP": "minutes"}
    )
    df["player_id"] = df["Player"].map(normalize_name_key)
    df["player_name"] = df["Player"]
    df["season"] = season
    df["source_bref"] = True
    return df.drop(columns=["Player"])


# -------------------------------------------------------------------- merge --

NBA_API_METRIC_COLS = ["PTS", "REB", "AST", "TS_PCT", "EFG_PCT", "USG_PCT", "AST_PCT", "REB_PCT", "TOV_PCT", "PIE"]
BREF_METRIC_COLS = ["PER", "WS", "BPM", "VORP"]


def merge_season(season: str, unmatched_rows: list[dict]) -> pd.DataFrame | None:
    nba = load_nba_api_season(season)
    bref = load_bref_season(season)

    if nba is None and bref is None:
        return None

    if nba is None:
        out = bref.copy()
        for col in NBA_API_METRIC_COLS:
            out[col] = np.nan
        out["source_nba_api"] = False
        return out

    if bref is None:
        out = nba.copy()
        for col in BREF_METRIC_COLS:
            out[col] = np.nan
        out["source_bref"] = False
        return out

    # Tier 1: exact match on the strict (suffix-preserving) player_id.
    bref_metrics = bref[["player_id", *BREF_METRIC_COLS]]
    merged = nba.merge(bref_metrics, on="player_id", how="left")

    exact_matched_ids = set(nba["player_id"]) & set(bref["player_id"])
    unmatched_bref = bref[~bref["player_id"].isin(exact_matched_ids)].copy()

    # Tier 2: same-season fallback on the suffix-stripped loose key, only for
    # bref rows tier 1 missed and nba rows that themselves had no exact bref
    # match (so we never re-attach metrics onto an nba player who already
    # matched). A loose key that maps to more than one nba player this season
    # is genuinely ambiguous and is left for tier 1's "still unmatched" path.
    if not unmatched_bref.empty:
        unmatched_bref["loose_key"] = unmatched_bref["player_id"].map(loose_key)
        nba_candidates = nba.loc[~nba["player_id"].isin(exact_matched_ids), ["player_id"]].copy()
        nba_candidates["loose_key"] = nba_candidates["player_id"].map(loose_key)

        fallback = unmatched_bref.merge(
            nba_candidates, on="loose_key", how="inner", suffixes=("_bref", "_nba")
        )
        dup_mask = fallback["loose_key"].duplicated(keep=False)
        fallback = fallback[~dup_mask]

        if not fallback.empty:
            attach = fallback[["player_id_nba", *BREF_METRIC_COLS]].rename(columns={"player_id_nba": "player_id"})
            merged = merged.merge(attach, on="player_id", how="left", suffixes=("", "_fallback"))
            for col in BREF_METRIC_COLS:
                merged[col] = merged[col].combine_first(merged[f"{col}_fallback"])
                merged = merged.drop(columns=[f"{col}_fallback"])

            matched_via_fallback = set(fallback["player_id_bref"])
            unmatched_bref = unmatched_bref[~unmatched_bref["player_id"].isin(matched_via_fallback)]
        unmatched_bref = unmatched_bref.drop(columns=["loose_key"])

    if not unmatched_bref.empty:
        extra = unmatched_bref.copy()
        for col in NBA_API_METRIC_COLS:
            extra[col] = np.nan
        extra["source_nba_api"] = False
        extra = extra[merged.columns]
        merged = pd.concat([merged, extra], ignore_index=True)
        for _, row in unmatched_bref.iterrows():
            unmatched_rows.append({"season": season, "player_name": row["player_name"], "player_id": row["player_id"]})

    return merged


def flag_age_decreases(player_seasons: pd.DataFrame) -> pd.DataFrame:
    """Safety net for normalize_name_key()'s suffix-stripping: a player's age
    should never decrease from one season to the next. If it does, two
    different real people almost certainly got merged under one player_id.
    Returns the offending rows (empty if none) -- callers log but don't fail
    the build on this, since it's a data-quality signal, not a hard error.
    """
    df = player_seasons.sort_values(["player_id", "season"]).copy()
    df["prev_age"] = df.groupby("player_id")["age"].shift(1)
    return df[df["age"] < df["prev_age"]]


def build_player_seasons() -> pd.DataFrame:
    all_years = sorted(set(range(NBA_API_START_YEAR, NBA_API_END_YEAR + 1)) | set(range(BREF_START_YEAR, BREF_END_YEAR + 1)))
    seasons = [season_str(y) for y in all_years]

    unmatched_rows: list[dict] = []
    frames = []
    for season in seasons:
        merged = merge_season(season, unmatched_rows)
        if merged is not None:
            frames.append(merged)
            print(f"  {season}: {len(merged)} player-season rows")
        else:
            print(f"  {season}: no data (skipped)")

    if unmatched_rows:
        pd.DataFrame(unmatched_rows).to_csv(REPORT_PATH, index=False)
        print(f"\n{len(unmatched_rows)} Basketball-Reference rows had no nba_api match "
              f"(kept with nba_api metrics as NaN) -- logged to {REPORT_PATH}")

    full = pd.concat(frames, ignore_index=True)
    full["age"] = pd.to_numeric(full["age"], errors="coerce")
    full["games_played"] = pd.to_numeric(full["games_played"], errors="coerce")
    full["minutes"] = pd.to_numeric(full["minutes"], errors="coerce")
    full = full.dropna(subset=["age", "player_id"])
    full["age"] = full["age"].astype(int)

    ordered_cols = [
        "player_id", "player_name", "season", "age", "games_played", "minutes",
        *NBA_API_METRIC_COLS, *BREF_METRIC_COLS,
        "source_nba_api", "source_bref",
    ]
    return full[ordered_cols]


def build_players_table(player_seasons: pd.DataFrame) -> pd.DataFrame:
    def _pick_display_name(names: pd.Series) -> str:
        return names.value_counts().idxmax()

    grouped = player_seasons.groupby("player_id").agg(
        display_name=("player_name", _pick_display_name),
        first_season=("season", "min"),
        last_season=("season", "max"),
        season_count=("season", "count"),
    )
    return grouped.reset_index()


def write_sqlite(player_seasons: pd.DataFrame, players: pd.DataFrame) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        player_seasons.to_sql("player_seasons", conn, if_exists="replace", index=False)
        players.to_sql("players", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ps_player ON player_seasons(player_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ps_age ON player_seasons(age)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ps_season ON player_seasons(season)")


def main() -> None:
    print("Building player_seasons from cached raw data...")
    player_seasons = build_player_seasons()
    print(f"\nTotal player-season rows: {len(player_seasons)}")

    age_decreases = flag_age_decreases(player_seasons)
    if not age_decreases.empty:
        report_path = ROOT / "data" / "processed" / "suspicious_player_id_age_decreases.csv"
        age_decreases.to_csv(report_path, index=False)
        print(
            f"WARNING: {len(age_decreases)} rows have age decreasing from the prior season "
            f"for the same player_id -- likely two different real people merged by "
            f"normalize_name_key(). Logged to {report_path} for review."
        )
    else:
        print("Sanity check passed: no player_id has age decreasing across consecutive seasons.")

    players = build_players_table(player_seasons)
    print(f"Total distinct players: {len(players)}")

    write_sqlite(player_seasons, players)
    print(f"Wrote {DB_PATH}")

    lebron = players[players["display_name"].str.contains("LeBron", case=False, na=False)]
    print("\nSpot check -- LeBron James rows found:")
    print(lebron)


if __name__ == "__main__":
    main()
