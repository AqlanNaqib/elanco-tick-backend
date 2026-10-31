"""The REST API. Run: uvicorn app.main:app --reload --port 8080"""
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from app.models import IngestionRun, RejectedRecord, Sighting
from pydantic import BaseModel
from sqlmodel import Session, col, func, select

from app.database import create_db, engine
from app.models import Sighting
from app.insights import find_spikes
from app.regions import region_for

log = logging.getLogger("tick_api")

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


app = FastAPI(
    title="Tick Sightings API",
    description="Search, filter and analyse UK tick sightings.",
    lifespan=lifespan,
)

@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    log.exception("Unexpected error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

def get_session():
    with Session(engine) as session:
        yield session

class HealthStatus(BaseModel):
    status: str

class RegionStat(BaseModel):
    region: str
    count: int
    cities: dict[str, int]

class TrendPoint(BaseModel):
    period: str
    count: int

class Spike(BaseModel):
    location: str
    region: str
    period: str
    count: int
    usual: float
    z_score: float

class DataQuality(BaseModel):
    last_run: IngestionRun
    rejected_reasons: dict[str, int]
    rows_in_database: int

class SightingPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[Sighting]


def apply_filters(query, start, end, location, species):
    """Adds the optional filters shared by several endpoints."""
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="start must be on or before end")
    if start:
        query = query.where(Sighting.date >= datetime.combine(start, time.min, timezone.utc))
    if end:

        next_day = datetime.combine(end + timedelta(days=1), time.min, timezone.utc)
        query = query.where(Sighting.date < next_day)
    if location:
        query = query.where(func.lower(Sighting.location) == location.strip().lower())
    if species:
        query = query.where(func.lower(Sighting.species) == species.strip().lower())
    return query


@app.get("/health", response_model=HealthStatus, tags=["General"])
def health():
    return {"status": "ok"}


@app.get("/sightings", response_model=SightingPage, tags=["Sightings"])
def list_sightings(
    start: date | None = Query(None, description="Earliest date, e.g. 2020-01-01"),
    end: date | None = Query(None, description="Latest date, inclusive"),
    location: str | None = Query(None, description="City, case-insensitive"),
    species: str | None = Query(None, description="Species, case-insensitive"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    query = apply_filters(select(Sighting), start, end, location, species)
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    items = session.exec(
        query.order_by(col(Sighting.date).desc()).offset(offset).limit(limit)
    ).all()
    return SightingPage(total=total, limit=limit, offset=offset, items=items)


@app.get("/sightings/{sighting_id}", response_model=Sighting, tags=["Sightings"])
def get_sighting(sighting_id: str, session: Session = Depends(get_session)):
    sighting = session.get(Sighting, sighting_id)
    if not sighting:
        raise HTTPException(status_code=404, detail="Sighting not found")
    return sighting


@app.get("/stats/regions", response_model=list[RegionStat], tags=["Stats"])
def sightings_per_region(
    start: date | None = None,
    end: date | None = None,
    species: str | None = None,
    session: Session = Depends(get_session),
):
    query = select(Sighting.location, func.count()).group_by(Sighting.location)
    rows = session.exec(apply_filters(query, start, end, None, species)).all()

    regions: dict[str, dict] = {}
    for city, count in rows:
        region = regions.setdefault(region_for(city), {"count": 0, "cities": {}})
        region["count"] += count
        region["cities"][city] = count

    return sorted(
        ({"region": name, **data} for name, data in regions.items()),
        key=lambda r: r["count"],
        reverse=True,
    )


@app.get("/stats/trends", response_model=list[TrendPoint], tags=["Stats"])
def sightings_over_time(
    interval: Literal["week", "month"] = "month",
    start: date | None = None,
    end: date | None = None,
    location: str | None = None,
    species: str | None = None,
    session: Session = Depends(get_session),
):

    fmt = "%Y-%m" if interval == "month" else "%Y-W%W"
    period = func.strftime(fmt, Sighting.date).label("period")
    query = select(period, func.count()).group_by(period).order_by(period)
    rows = session.exec(apply_filters(query, start, end, location, species)).all()
    return [{"period": p, "count": c} for p, c in rows]

@app.get("/insights/spikes", response_model=list[Spike], tags=["Insights"])
def sighting_spikes(
    threshold: float = Query(2.0, ge=1.0, le=5.0, description="How unusual a month must be, in standard deviations"),
    min_count: int = Query(3, ge=1, description="Ignore months with fewer sightings than this"),
    location: str | None = None,
    species: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Months where a city had far more sightings than its previous 12 months."""
    query = apply_filters(select(Sighting.date, Sighting.location), None, None, location, species)
    rows = session.exec(query).all()
    return find_spikes(rows, threshold=threshold, min_count=min_count)[:limit]

@app.get("/stats/data-quality", response_model=DataQuality, tags=["Stats"])
def data_quality(session: Session = Depends(get_session)):
    """What happened to the data on the last pipeline run."""
    run = session.exec(select(IngestionRun).order_by(col(IngestionRun.id).desc())).first()
    if not run:
        raise HTTPException(status_code=404, detail="No data has been loaded yet. Run python -m app.refresh")

    reasons = session.exec(
        select(RejectedRecord.reason, func.count())
        .where(RejectedRecord.run_id == run.id)
        .group_by(RejectedRecord.reason)
    ).all()
    rows = session.exec(select(func.count()).select_from(Sighting)).one()
    return DataQuality(last_run=run, rejected_reasons=dict(reasons), rows_in_database=rows)