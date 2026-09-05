from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import aging_curve, metrics, players
from app.core.cache_repository import get_repository

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        repo = get_repository()
        print(f"Cache loaded: {len(repo.player_seasons)} player-season rows, {len(repo.players)} players.")
    except FileNotFoundError as exc:
        print(f"WARNING: {exc}")
    yield


app = FastAPI(title="Father Time: NBA Aging Curve Anomaly Detector", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(aging_curve.router)
app.include_router(metrics.router)


@app.get("/health")
def health():
    return {"status": "ok"}


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
