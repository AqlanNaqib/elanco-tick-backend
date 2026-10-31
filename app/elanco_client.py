"""Talks to the Elanco API and retries the kind of failures that usually fix themselves."""
import logging
import time
from datetime import datetime, timezone

import httpx

BASE_URL = "https://dev-task.elancoapps.com/data"

RETRY_STATUSES = {429, 500, 502, 503, 504}

log = logging.getLogger(__name__)


class UpstreamError(Exception):
    """Raised when the Elanco API can't be reached or keeps failing."""


def get_json(client, path, retries=3, wait_seconds=2):
    """GETs a path and returns the JSON, retrying temporary failures."""
    for attempt in range(1, retries + 1):
        try:
            response = client.get(path)
            if response.status_code < 400:
                return response.json()
            if response.status_code not in RETRY_STATUSES:
                raise UpstreamError(f"GET {path} failed with status {response.status_code}")
            problem = f"status {response.status_code}"
        except httpx.TransportError:
            problem = "network error"

        if attempt < retries:
            log.warning("GET %s: %s, trying again in %ss (attempt %s of %s)",
                        path, problem, wait_seconds, attempt, retries)
            time.sleep(wait_seconds)
            wait_seconds *= 2 

    raise UpstreamError(f"GET {path} still failing after {retries} attempts ({problem})")


def fetch_snapshot():
    """Gets every sighting plus the API's own total, ready to save to disk."""
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        stats = get_json(client, "/stats")
        sightings = get_json(client, "/tick-sightings")

    if not isinstance(sightings, list):
        raise UpstreamError("expected a list of sightings from /tick-sightings")

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "reported_total": stats.get("total_sightings"),
        "received": len(sightings),
        "sightings": sightings,
    }