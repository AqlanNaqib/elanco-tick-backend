"""Database tables."""
from datetime import datetime

from sqlmodel import Field, SQLModel


class Sighting(SQLModel, table=True):
    id: str = Field(primary_key=True)
    date: datetime = Field(index=True)
    location: str = Field(index=True)
    species: str = Field(index=True)
    latin_name: str

    source: str = Field(default="elanco", index=True)


class IngestionRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    ran_at: datetime
    source: str  
    reported_total: int | None = None
    received: int = 0
    inserted: int = 0
    updated: int = 0
    duplicates: int = 0
    rejected: int = 0


class RejectedRecord(SQLModel, table=True):
    pk: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="ingestionrun.id", index=True)
    raw: str
    reason: str