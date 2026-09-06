"""Rule-based classification of a player's aging-curve *shape* into a
human-readable archetype, purely from already-computed anomaly data.
Zero I/O, deterministic, no ML — same philosophy as the rest of /analysis.
"""
from dataclasses import dataclass
from statistics import pstdev

from app.analysis.anomaly import CareerSummary, TrajectoryPoint

CONSISTENCY_STD_THRESHOLD = 0.35
DECLINE_DROP_THRESHOLD = 1.0
RISE_THRESHOLD = 0.5
SHORT_CAREER_SEASONS = 6
LONG_CAREER_SEASONS = 15


@dataclass(frozen=True)
class Archetype:
    label: str
    tagline: str


def classify_archetype(points: list[TrajectoryPoint], summary: CareerSummary) -> Archetype | None:
    """Classify shape of the z-score trajectory. Returns None when there
    isn't enough high-confidence data to say anything meaningful.
    """
    scored = [p for p in points if p.z_score is not None and not p.low_confidence]
    if len(scored) < 3:
        return None

    zs = [p.z_score for p in scored]
    n = len(scored)
    half = n // 2
    first_half_avg = sum(zs[:half]) / half
    second_half_avg = sum(zs[half:]) / (n - half)
    peak_z = max(zs)
    peak_idx = zs.index(peak_z)
    end_avg = sum(zs[-min(3, n):]) / min(3, n)
    spread = pstdev(zs)
    seasons = summary.qualifying_season_count
    career_index = summary.career_anomaly_index or 0.0

    # Order matters: most specific / most fun claims first, generic last.
    if career_index > 1.0 and seasons >= LONG_CAREER_SEASONS and end_avg > peak_z - 0.5:
        return Archetype(
            "Defying Father Time",
            f"{seasons} qualifying seasons and still nowhere near the historical baseline late in his career.",
        )
    if peak_z > 1.5 and (seasons < SHORT_CAREER_SEASONS or (peak_idx < n - 1 and end_avg < peak_z - DECLINE_DROP_THRESHOLD)):
        return Archetype("Flash in the Pan", f"Peaked at +{peak_z:.1f} SD, but it didn't last.")
    if second_half_avg - first_half_avg > RISE_THRESHOLD:
        return Archetype("Late Bloomer", "Got better relative to his age-cohort as his career went on, not worse.")
    if spread < CONSISTENCY_STD_THRESHOLD and abs(career_index) > 0.3:
        return Archetype("Remarkably Consistent", "Almost the same distance from the baseline at every age — no real peak or decline.")
    if peak_idx < n * 0.3 and peak_z - end_avg > DECLINE_DROP_THRESHOLD:
        return Archetype("Early Peak, Fast Decline", "Was way ahead of the aging curve early, then fell back toward it fast.")
    if abs(career_index) < 0.3:
        return Archetype("Textbook Aging Curve", "Tracks the historical age baseline about as closely as anyone could.")
    return None
