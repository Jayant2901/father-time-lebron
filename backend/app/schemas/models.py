from pydantic import BaseModel


class PlayerSummary(BaseModel):
    player_id: str
    display_name: str
    first_season: str
    last_season: str
    season_count: int


class TrajectoryPointOut(BaseModel):
    age: int
    season: str
    value: float
    percentile: float
    cohort_mean: float | None
    cohort_std: float | None
    cohort_n: int
    z_score: float | None
    low_confidence: bool


class CareerSummaryOut(BaseModel):
    career_anomaly_index: float | None
    peak_anomaly_age: int | None
    top_5_pct_season_count: int
    qualifying_season_count: int


class ArchetypeOut(BaseModel):
    label: str
    tagline: str


class AgingCurveMetricResult(BaseModel):
    metric: str
    display_name: str
    unit: str
    points: list[TrajectoryPointOut]
    summary: CareerSummaryOut
    archetype: ArchetypeOut | None = None


class AgingCurveResponse(BaseModel):
    player: PlayerSummary
    results: list[AgingCurveMetricResult]


class BaselinePoint(BaseModel):
    age: int
    mean: float
    std: float
    n: int
    low_confidence: bool


class BaselineResponse(BaseModel):
    metric: str
    display_name: str
    unit: str
    min_minutes: float
    min_games: int
    min_seasons: int
    points: list[BaselinePoint]


class ComparePlayerOut(BaseModel):
    player_id: str
    display_name: str
    headshot_url: str | None
    qualifying_season_count: int
    avg_percentile: float | None
    career_anomaly_index: float | None


class CompareResponse(BaseModel):
    metric: str
    display_name: str
    unit: str
    players: list[ComparePlayerOut]
    verdict: str | None = None


class MetricInfo(BaseModel):
    key: str
    display_name: str
    higher_is_better: bool
    source: str
    earliest_season: str | None
    unit: str
