"""
Loads the raw snapshot, validates and cleans each record, and saves it to SQLite.

Run from the project root:  python -m app.ingest
Safe to run more than once: existing rows are updated, not duplicated.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from sqlmodel import Session

from app.cleaning import clean
from app.database import create_db, engine
from app.models import IngestionRun, RejectedRecord, Sighting
from app.schemas import RawSighting

RAW_PATH = Path("data/raw.json")

log = logging.getLogger(__name__)


def ingest(raw_path: Path = RAW_PATH, source: str = "snapshot") -> dict:
    snapshot = json.loads(raw_path.read_text(encoding="utf-8"))
    records = snapshot["sightings"]
    run = IngestionRun(ran_at=datetime.now(timezone.utc), source=source,
                       reported_total=snapshot.get("reported_total"), received=len(records))

    if run.reported_total is not None and run.reported_total != run.received:
        log.warning("Elanco reports %s sightings but we received %s",
                    run.reported_total, run.received)

    seen = set()
    create_db()
    with Session(engine) as session:
        session.add(run)
        session.flush()  

        for raw in records:
            try:
                sighting = clean(RawSighting.model_validate(raw))
            except ValidationError as error:
                first = error.errors()[0]
                field = first["loc"][0] if first["loc"] else "record"
                reason = f"{field}: {first['msg']}"
                session.add(RejectedRecord(run_id=run.id, raw=json.dumps(raw), reason=reason))
                run.rejected += 1
                continue

            key = (sighting.date, sighting.location, sighting.species)
            if key in seen:
                run.duplicates += 1
                continue
            seen.add(key)

            existing = session.get(Sighting, sighting.id)
            if existing:
                existing.date = sighting.date
                existing.location = sighting.location
                existing.species = sighting.species
                existing.latin_name = sighting.latin_name
                run.updated += 1
            else:
                session.add(sighting)
                run.inserted += 1

        report = run.model_dump(exclude={"id", "ran_at"})
        session.commit()
    return report


if __name__ == "__main__":
    print(ingest())