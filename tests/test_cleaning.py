"""Tests for validation and cleaning of raw Elanco records."""
import pytest
from pydantic import ValidationError

from app.cleaning import clean
from app.schemas import RawSighting

GOOD = {"id": "x1", "date": "2023-05-01T10:00:00", "location": " london ",
        "species": "fox/BADGER  tick", "latinName": "ixodes canisuga"}


def test_messy_text_is_tidied():
    sighting = clean(RawSighting.model_validate(GOOD))
    assert sighting.location == "London"
    assert sighting.species == "Fox/badger tick"
    assert sighting.latin_name == "Ixodes canisuga"


def test_date_without_timezone_is_treated_as_utc():
    sighting = clean(RawSighting.model_validate(GOOD))
    assert sighting.date.utcoffset().total_seconds() == 0


@pytest.mark.parametrize("change", [
    {"date": "not a date"},
    {"date": "2099-01-01T00:00:00"},
    {"location": ""},
    {"species": None},
])
def test_bad_records_are_rejected(change):
    with pytest.raises(ValidationError):
        RawSighting.model_validate({**GOOD, **change})


def test_missing_field_is_rejected():
    record = {k: v for k, v in GOOD.items() if k != "location"}
    with pytest.raises(ValidationError):
        RawSighting.model_validate(record)