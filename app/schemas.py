from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator


class RawSighting(BaseModel):
    id: str = Field(min_length=1)
    date: datetime
    location: str = Field(min_length=1)
    species: str = Field(min_length=1)
    latinName: str = Field(min_length=1)

    @field_validator("date")
    @classmethod
    def check_date(cls, value: datetime) -> datetime:

        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        if value > datetime.now(timezone.utc):
            raise ValueError("date is in the future")
        return value