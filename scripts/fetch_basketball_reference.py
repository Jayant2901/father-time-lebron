"""Phase A2: scrape season-level Advanced leaderboard tables from
Basketball-Reference -- the only source for PER, WS, BPM, VORP, and the
only source that covers the full 1946-47 BAA/NBA history the user chose.

One request per season (not per player) via the /leagues/NBA_{end_year}_advanced.html
page, which lists every player who appeared that season in one HTML table.

Basketball-Reference sits behind a Cloudflare bot challenge that a plain
`requests` GET cannot pass (confirmed during development: a normal request
gets a 403 "Just a moment..." JS-challenge page, not the real page). We use
`cloudscraper`, which solves that challenge, instead of `requests` here.

Raw HTML is cached to data/raw/bref/{season}_advanced.html, one file per
season, gitignored. Re-running skips any season already on disk.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import cloudscraper
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _seasons import BREF_END_YEAR, BREF_START_YEAR, season_str  # noqa: E402

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "bref"
REQUEST_TIMEOUT = 30
SLEEP_BETWEEN_CALLS = 3.5

_scraper = cloudscraper.create_scraper()


@retry(stop=stop_after_attempt(3), wait=wait_exponential_jitter(initial=3, max=30))
def _fetch_html(end_year: int) -> str:
    url = f"https://www.basketball-reference.com/leagues/NBA_{end_year}_advanced.html"
    resp = _scraper.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    # basketball-reference's Content-Type header omits a charset, so requests
    # falls back to ISO-8859-1 per RFC 2616 even though the body is actually
    # UTF-8 -- left uncorrected, every accented name (Jokić, Dončić, ...)
    # comes out mangled. Force the correct encoding before reading .text.
    resp.encoding = "utf-8"
    if len(resp.text) < 5000:
        # A too-short response is almost certainly a challenge/error page
        # that slipped past raise_for_status(), not real table data.
        raise RuntimeError(f"suspiciously short response ({len(resp.text)} bytes) for {url}")
    return resp.text


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    seasons = [season_str(y) for y in range(BREF_START_YEAR, BREF_END_YEAR + 1)]
    print(f"Fetching {len(seasons)} seasons ({seasons[0]} .. {seasons[-1]}) from Basketball-Reference")

    for start_year, season in zip(range(BREF_START_YEAR, BREF_END_YEAR + 1), seasons):
        out_path = RAW_DIR / f"{season}_advanced.html"
        if out_path.exists():
            print(f"[skip] {out_path.name} already cached")
            continue
        end_year = start_year + 1
        print(f"[fetch] {season} (NBA_{end_year}_advanced.html) ...", end=" ", flush=True)
        try:
            html = _fetch_html(end_year)
        except Exception as exc:  # noqa: BLE001 -- log and keep going to the next season
            print(f"FAILED after retries: {exc}")
            continue
        out_path.write_text(html, encoding="utf-8")
        print(f"ok ({len(html)} bytes)")
        time.sleep(SLEEP_BETWEEN_CALLS)

    print("Done.")


if __name__ == "__main__":
    main()
