# Data acquisition (nba_api + Basketball-Reference scraping) is a one-time
# batch job that already ran locally to produce data/processed/nba_aging.db.
# That db is baked into the image at BUILD time (not fetched at container
# start) because most free hosting tiers have ephemeral filesystems -- the
# running app only ever reads the file that was copied in below.
FROM python:3.13-slim

WORKDIR /app

COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY data/processed/nba_aging.db data/processed/nba_aging.db

EXPOSE 8000

# Shell form so $PORT (set by most PaaS hosts, e.g. Render) is honored, with
# 8000 as a sane local-Docker default when it's unset.
CMD uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000}
