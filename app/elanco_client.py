"""Talks to the Elanco API, retrying the failures that are usually temporary."""
import logging
import time
from datetime import datetime, timezone

import httpx

BASE_URL = "https://dev-task.elancoapps.com/data"
RETRY_STATUSES = {429, 500, 502, 503, 504}

log = logging.getLogger(__name__)


class UpstreamError(Exception):
    """The Elanco API could not be reached, or kept failing."""


def get_json(client: httpx.Client, path: str, retries: int = 3, backoff: float = 2.0):
    problem = ""
    for attempt in range(1, retries + 1):
        try:
            response = client.get(path)
        except httpx.TransportError as error:
            problem = f"network error ({type(error).__name__})"
        else:
            if response.status_code < 400:
                return response.json()
            if response.status_code not in RETRY_STATUSES:
                raise UpstreamError(f"GET {path} failed with status {response.status_code}")
            problem = f"status {response.status_code}"

        if attempt < retries:
            wait = backoff * 2 ** (attempt - 1)
            log.warning("GET %s: %s, retrying in %.0fs (attempt %d of %d)",
                        path, problem, wait, attempt, retries)
            time.sleep(wait)

    raise UpstreamError(f"GET {path} still failing after {retries} attempts: {problem}")


def fetch_snapshot(client: httpx.Client | None = None) -> dict:
    """Fetches every sighting plus the API's own total, ready to save to disk."""
    own_client = client is None
    client = client or httpx.Client(base_url=BASE_URL, timeout=30)
    try:
        stats = get_json(client, "/stats")
        sightings = get_json(client, "/tick-sightings")
    finally:
        if own_client:
            client.close()

    if not isinstance(sightings, list):
        raise UpstreamError("expected a list of sightings from /tick-sightings")

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "reported_total": stats.get("total_sightings"),
        "received": len(sightings),
        "sightings": sightings,
    }