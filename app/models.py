from datetime import datetime

from sqlmodel import Field, SQLModel


class Sighting(SQLModel, table=True):
    id: str = Field(primary_key=True)

    date: datetime = Field(index=True)
    location: str = Field(index=True)
    species: str = Field(index=True)
    latin_name: str

    source: str = Field(default="elanco", index=True)


class RejectedRecord(SQLModel, table=True):

    pk: int | None = Field(default=None, primary_key=True)
    raw: str
    reason: str
    rejected_at: datetime