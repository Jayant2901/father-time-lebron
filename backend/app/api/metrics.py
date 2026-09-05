from fastapi import APIRouter

from app.core.config import METRICS
from app.schemas.models import MetricInfo

router = APIRouter()


@router.get("/metrics", response_model=list[MetricInfo])
def list_metrics():
    return [
        MetricInfo(
            key=m.key,
            display_name=m.display_name,
            higher_is_better=m.higher_is_better,
            source=m.source,
            earliest_season=m.earliest_season,
            unit=m.unit,
        )
        for m in METRICS.values()
    ]
