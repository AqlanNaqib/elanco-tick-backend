"""
Fetches fresh data from Elanco and loads it into the database.
If Elanco is down, it falls back to the last saved snapshot so the API keeps working.

Run from the project root:  python -m app.refresh
"""
import json
import logging

from app.elanco_client import UpstreamError, fetch_snapshot
from app.ingest import RAW_PATH, ingest

log = logging.getLogger(__name__)


def refresh() -> dict:
    try:
        snapshot = fetch_snapshot()
        RAW_PATH.parent.mkdir(exist_ok=True)
        RAW_PATH.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        source = "live"
    except UpstreamError as error:
        if not RAW_PATH.exists():
            raise  
        log.error("Elanco API unavailable (%s). Using the last saved snapshot.", error)
        source = "snapshot"

    return ingest(RAW_PATH, source=source)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    print(refresh())