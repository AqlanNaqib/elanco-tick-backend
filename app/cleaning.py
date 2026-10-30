from app.models import Sighting
from app.schemas import RawSighting


def tidy(text: str) -> str:
    return " ".join(text.split()).capitalize()


def tidy_city(text: str) -> str:
    return " ".join(text.split()).title()


def clean(raw: RawSighting) -> Sighting:
    return Sighting(
        id=raw.id.strip(),
        date=raw.date,
        location=tidy_city(raw.location),
        species=tidy(raw.species),
        latin_name=tidy(raw.latinName),
    )