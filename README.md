# Father Time — NBA Aging-Curve Anomaly Detector

**Does LeBron actually age differently than NBA history says players should — or is that just a story we tell?**

This project answers that with statistics instead of vibes: it builds real aging curves from every qualifying NBA/BAA player-season since 1949-50, then measures how many standard deviations any player's performance sits above or below the historical norm *at their exact age*. LeBron is the flagship example (spoiler: he's +1.5 to +1.8 SD above the league's age-based baseline in Player Efficiency Rating at **every single age from 19 to 40**), but it works for any player in NBA history.

## Why this exists

A portfolio project meant to demonstrate, in one place:
- **Data engineering** — acquiring, cleaning, and joining two messy, semi-official data sources (stats.nba.com via `nba_api`, and a Cloudflare-protected Basketball-Reference scrape) into one canonical dataset, with real bugs found and fixed along the way (see [Data pipeline notes](#data-pipeline-notes--bugs-found-and-fixed)).
- **Statistical rigor** — era-normalization, population-vs-sample statistics, small-sample confidence handling — the exact kind of judgment call a good data science interview probes.
- **Backend/API design** — a real FastAPI service with tested endpoints, not a notebook.
- **Shipping** — a deployed, usable tool, not just code that runs on one machine.

## Quickstart

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

# Phase A: pull raw data and build the cache (takes ~10-15 minutes total, one-time)
python scripts/fetch_nba_api_data.py
python scripts/fetch_basketball_reference.py
python scripts/build_cache.py

# Phase C/D: run the app
uvicorn app.main:app --app-dir backend --reload
# -> http://127.0.0.1:8000            (frontend)
# -> http://127.0.0.1:8000/docs       (interactive API docs)
```

Run the test suite (uses synthetic fixtures, no data build required):

```bash
pytest
```

## How it works

### Data sources
- **nba_api** (wraps stats.nba.com), 1996-97 onward: per-100-possession counting stats (PTS, REB, AST) and advanced rate stats (TS%, eFG%, USG%, AST%, REB%, TOV%, PIE), pulled once per season via `LeagueDashPlayerStats` (not per player — ~3 requests per season covers the entire league).
- **Basketball-Reference**, 1949-50 onward: PER, Win Shares, Box Plus/Minus, and VORP — proprietary metrics nba_api doesn't expose at all. BR sits behind a Cloudflare bot challenge that a plain `requests` GET can't pass (confirmed during development — a normal request gets a 403 "Just a moment..." JS-challenge page); the fetch script uses `cloudscraper` instead.
- The two sources are joined per season on player identity (see below) and merged into one long-format table, `data/processed/nba_aging.db` (SQLite, gitignored/regeneratable). The running app never calls either external source — acquisition is a one-time batch job.

### Methodology
1. **Qualifying threshold**: a player-season counts only at ≥800 total minutes and ≥40 games (tunable via API query params).
2. **Era normalization**: rather than comparing raw stats across decades of wildly different pace and 3-point volume, every player-season is converted to a **within-season percentile rank** (0–100) among that season's qualifying players — the same idea as baseball's OPS+/ERA+.
3. **Age baseline**: percentiles are pooled by age across all cohort-eligible players (≥3 qualifying seasons, to keep short/fringe careers from skewing "typical"), giving a mean/std/n at every age from historical data alone.
4. **Anomaly score**: a player's z-score at each age = `(their percentile − age-cohort mean) / age-cohort std`. A minutes-weighted average across a career gives the **Career Anomaly Index**; peak-anomaly age and top-5%-league-wide season count are also surfaced.
5. **Small-sample honesty**: ages with a thin historical cohort (fewer than 15 qualifying player-seasons — very old ages, or early BAA years) are flagged `low_confidence` and rendered faded/dashed in the UI rather than presented with false confidence.

### API
| Endpoint | Purpose |
|---|---|
| `GET /players?search=...` | Name search |
| `GET /players/{player_id}/aging-curve?metrics=PTS,TS_PCT,PER` | Per-age trajectory + career summary for one or more metrics |
| `GET /baseline?metric=PTS` | The league-wide age baseline alone |
| `GET /metrics` | Metadata for every supported metric (source, earliest season, unit) |
| `GET /health` | Health check |

Full interactive docs at `/docs` once running.

## Caveats

- **PER/WS/BPM/VORP only go back to Basketball-Reference's coverage** (1949-50); nba_api-sourced rate stats (TS%, USG%, etc.) only start in 1996-97. Earlier seasons naturally have fewer available metrics per player-season — this is a real historical data gap, not a bug, and `/metrics` documents each metric's earliest season.
- **STL/BLK weren't tracked before 1973-74, and there was no 3-point line before 1979-80** — any metric depending on those is legitimately NaN for earlier seasons.
- **Cross-source player identity is name-based** (no shared ID exists across nba_api and Basketball-Reference for pre-1996 players). A two-tier matching scheme (exact suffix-preserving match, then a same-season suffix-stripped fallback) resolves the vast majority of cases correctly — verified against real father/son NBA duos (Tim Hardaway Jr., Larry Nance Jr., etc., both sources include the suffix) and single-person spelling inconsistencies (nba_api's "Jimmy Butler III" vs BR's "Jimmy Butler"). A small residual (~46 of 24,821 rows, ~0.2%) are genuine same-name collisions between two different, unrelated real players from decades where neither source disambiguates by suffix at all (e.g. two different players both called "Charles Jones" across NBA history) — this is a known, logged limitation (`data/processed/suspicious_player_id_age_decreases.csv` after running `build_cache.py`), not something solvable without a stable source-side player ID. None of the affected names are commonly searched stars.
- **Thresholds are judgment calls** (minimum minutes/games/seasons, low-confidence cutoff) — defaulted to reasonable values but exposed as tunable API parameters rather than hidden constants, since they're genuinely debatable.

## Data pipeline notes — bugs found and fixed

Two real bugs surfaced while building this, both worth knowing about if you extend the pipeline:
1. **Character encoding**: Basketball-Reference's `Content-Type` header omits a charset, so `requests`/`cloudscraper` default to ISO-8859-1 per RFC 2616 even though the actual content is UTF-8 — every accented name (Jokić, Dončić, Nesterović, ...) came out mangled until `resp.encoding` was forced to `"utf-8"` before reading `.text`.
2. **Name-matching false negatives from over-aggressive suffix stripping**: an early version of the cross-source join stripped generational suffixes (Jr./Sr./II/III) to reconcile cases like nba_api's "Jimmy Butler III" vs BR's "Jimmy Butler" — but this accidentally merged real father/son duos (Larry Nance and Larry Nance Jr., Tim Hardaway and Tim Hardaway Jr.) into one fictitious player_id, since BR *does* distinguish those pairs by suffix. The fix: try an exact suffix-preserving match first, and only fall back to a suffix-stripped match within the same season for genuine single-person spelling gaps. A monotonic-age check (a real player's age should never decrease season-to-season) now runs after every build as a safety net and would have caught this class of bug immediately.

## Deploying (Render)

The repo includes `render.yaml`, so deployment is a Blueprint away:

1. Go to [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint**.
2. Connect the `nba-aging-curves` GitHub repo (grant Render access if this is its first time seeing your account).
3. Render reads `render.yaml` and provisions a free Docker web service automatically — no manual config needed, since the Dockerfile already bakes in `data/processed/nba_aging.db`.
4. Once deployed, hit `<your-render-url>/health` and `<your-render-url>/docs` to confirm, then load the root URL for the frontend.

Free-tier Render services spin down after inactivity and take ~30-60s to wake back up on the next request — normal, not a bug.

## Project layout

```
scripts/                   data acquisition + cache-build (batch, run once)
backend/app/analysis/      pure statistical functions (percentile, aging curve, anomaly) -- zero I/O, fully unit-tested
backend/app/api/           FastAPI route handlers
backend/app/core/          config constants, metric metadata, cache repository
backend/app/schemas/       pydantic response models
backend/tests/             pytest suite (synthetic-data unit tests + FastAPI TestClient integration tests)
frontend/                  static HTML/CSS/JS (Chart.js via CDN), no build step
```
