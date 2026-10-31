"""
The REST API for the tick sightings.

Run it from the project root with:  uvicorn app.main:app --reload --port 8080
Then open http://localhost:8080/docs to try it in Swagger.
"""
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.database import create_db, engine
from app.insights import find_spikes
from app.models import IngestionRun, RejectedRecord, Sighting
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


class SightingPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[Sighting]


class RegionStat(BaseModel):
    region: str
    count: int
    cities: dict[str, int]


class TrendPoint(BaseModel):
    period: str
    count: int


class DataQuality(BaseModel):
    last_run: IngestionRun
    rejected_reasons: dict[str, int]
    rows_in_database: int


class Spike(BaseModel):
    location: str
    region: str
    period: str
    count: int
    usual: float
    z_score: float



def apply_filters(query, start, end, location, species):
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="start must be on or before end")

    if start:
        start_of_day = datetime.combine(start, time.min, timezone.utc)
        query = query.where(Sighting.date >= start_of_day)

    if end:
        start_of_next_day = datetime.combine(end + timedelta(days=1), time.min, timezone.utc)
        query = query.where(Sighting.date < start_of_next_day)

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
    location: str | None = Query(None, description="City (capitals don't matter)"),
    species: str | None = Query(None, description="Species (capitals don't matter)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    count_query = apply_filters(select(func.count()).select_from(Sighting), start, end, location, species)
    total = session.exec(count_query).one()

    query = apply_filters(select(Sighting), start, end, location, species)
    query = query.order_by(Sighting.date.desc()).offset(offset).limit(limit)
    items = session.exec(query).all()

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
    query = apply_filters(query, start, end, None, species)
    rows = session.exec(query).all()

    regions = {}
    for city, count in rows:
        region = region_for(city)
        if region not in regions:
            regions[region] = {"region": region, "count": 0, "cities": {}}
        regions[region]["count"] += count
        regions[region]["cities"][city] = count

    results = list(regions.values())
    results.sort(key=lambda r: r["count"], reverse=True)
    return results


@app.get("/stats/trends", response_model=list[TrendPoint], tags=["Stats"])
def sightings_over_time(
    interval: Literal["week", "month"] = "month",
    start: date | None = None,
    end: date | None = None,
    location: str | None = None,
    species: str | None = None,
    session: Session = Depends(get_session),
):
    if interval == "month":
        label_format = "%Y-%m"
    else:
        label_format = "%Y-W%W"

    period = func.strftime(label_format, Sighting.date)
    query = select(period, func.count()).group_by(period).order_by(period)
    query = apply_filters(query, start, end, location, species)
    rows = session.exec(query).all()

    return [{"period": label, "count": count} for label, count in rows]


@app.get("/stats/data-quality", response_model=DataQuality, tags=["Stats"])
def data_quality(session: Session = Depends(get_session)):
    """What happened to the data on the last load."""
    last_run = session.exec(select(IngestionRun).order_by(IngestionRun.id.desc())).first()
    if not last_run:
        raise HTTPException(status_code=404, detail="No data loaded yet. Run: python -m app.refresh")

    reasons_query = (
        select(RejectedRecord.reason, func.count())
        .where(RejectedRecord.run_id == last_run.id)
        .group_by(RejectedRecord.reason)
    )
    reasons = dict(session.exec(reasons_query).all())
    rows_in_database = session.exec(select(func.count()).select_from(Sighting)).one()

    return DataQuality(last_run=last_run, rejected_reasons=reasons, rows_in_database=rows_in_database)


@app.get("/insights/spikes", response_model=list[Spike], tags=["Insights"])
def sighting_spikes(
    threshold: float = Query(2.0, ge=1.0, le=5.0, description="How unusual a month has to be (z-score)"),
    min_count: int = Query(3, ge=1, description="Ignore months with fewer sightings than this"),
    location: str | None = None,
    species: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """Months where a city had a lot more sightings than in its previous 12 months."""
    query = apply_filters(select(Sighting.date, Sighting.location), None, None, location, species)
    rows = session.exec(query).all()
    spikes = find_spikes(rows, threshold=threshold, min_count=min_count)
    return spikes[:limit]