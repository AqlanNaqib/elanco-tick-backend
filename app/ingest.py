import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from sqlmodel import Session

from app.cleaning import clean
from app.database import create_db, engine
from app.models import RejectedRecord, Sighting
from app.schemas import RawSighting

RAW_PATH = Path("data/raw.json")


def ingest(raw_path: Path = RAW_PATH) -> dict:
    records = json.loads(raw_path.read_text(encoding="utf-8"))["sightings"]
    report = {"received": len(records), "inserted": 0, "updated": 0,
              "duplicates": 0, "rejected": 0}
    now = datetime.now(timezone.utc)
    seen = set()

    create_db()
    with Session(engine) as session:
        for raw in records:
            try:
                sighting = clean(RawSighting.model_validate(raw))
            except ValidationError as error:
                first = error.errors()[0]
                reason = f"{'.'.join(map(str, first['loc']))}: {first['msg']}"
                session.add(RejectedRecord(raw=json.dumps(raw), reason=reason, rejected_at=now))
                report["rejected"] += 1
                continue

            key = (sighting.date, sighting.location, sighting.species)
            if key in seen:
                report["duplicates"] += 1
                continue
            seen.add(key)

            existing = session.get(Sighting, sighting.id)
            if existing:
                existing.date = sighting.date
                existing.location = sighting.location
                existing.species = sighting.species
                existing.latin_name = sighting.latin_name
                report["updated"] += 1
            else:
                session.add(sighting)
                report["inserted"] += 1

        session.commit()
    return report


if __name__ == "__main__":
    print(ingest())