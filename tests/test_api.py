"""Tests for the REST endpoints."""


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_filter_by_location_is_case_insensitive(client):
    body = client.get("/sightings", params={"location": "london"}).json()
    assert body["total"] == 2
    assert {s["id"] for s in body["items"]} == {"a", "b"}


def test_filter_by_date_range_includes_end_date(client):
    body = client.get("/sightings", params={"start": "2024-01-01", "end": "2024-01-20"}).json()
    assert {s["id"] for s in body["items"]} == {"a", "b"}


def test_start_after_end_is_rejected(client):
    response = client.get("/sightings", params={"start": "2024-02-01", "end": "2024-01-01"})
    assert response.status_code == 400


def test_limit_out_of_range_is_rejected(client):
    assert client.get("/sightings", params={"limit": 1000}).status_code == 422


def test_unknown_sighting_returns_404(client):
    assert client.get("/sightings/nope").status_code == 404


def test_regions_group_cities(client):
    regions = {r["region"]: r for r in client.get("/stats/regions").json()}
    assert regions["London"]["count"] == 2
    assert regions["Yorkshire and the Humber"]["cities"] == {"Leeds": 1, "Sheffield": 1}


def test_monthly_trends(client):
    trends = client.get("/stats/trends", params={"start": "2024-01-01"}).json()
    assert trends == [{"period": "2024-01", "count": 2}, {"period": "2024-02", "count": 1}]


def test_invalid_interval_is_rejected(client):
    assert client.get("/stats/trends", params={"interval": "day"}).status_code == 422