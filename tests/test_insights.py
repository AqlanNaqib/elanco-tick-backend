"""Tests for spike detection."""
from datetime import datetime, timezone

from app.insights import find_spikes


def sightings(city, year, month, how_many):
    return [(datetime(year, month, 1, tzinfo=timezone.utc), city)] * how_many


def steady_year_then(final_count):
    rows = []
    for month in range(1, 13):
        rows += sightings("Leeds", 2023, month, 1)
    return rows + sightings("Leeds", 2024, 1, final_count)


def test_big_jump_is_flagged():
    spikes = find_spikes(steady_year_then(6))
    assert len(spikes) == 1
    assert spikes[0]["location"] == "Leeds"
    assert spikes[0]["period"] == "2024-01"
    assert spikes[0]["region"] == "Yorkshire and the Humber"


def test_normal_month_is_not_flagged():
    assert find_spikes(steady_year_then(1)) == []


def test_needs_a_full_year_of_history():
    rows = sightings("Leeds", 2024, 1, 1) + sightings("Leeds", 2024, 2, 1) + sightings("Leeds", 2024, 3, 9)
    assert find_spikes(rows) == []


def test_no_data_gives_no_spikes():
    assert find_spikes([]) == []