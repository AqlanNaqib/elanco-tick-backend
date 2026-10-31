"""Shared test setup: a throwaway in-memory database with a few known sightings."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.main import app, get_session
from app.models import Sighting


def utc(year, month, day):
    return datetime(year, month, day, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all([
            Sighting(id="a", date=utc(2024, 1, 10), location="London",
                     species="Marsh tick", latin_name="Ixodes apronophorus"),
            Sighting(id="b", date=utc(2024, 1, 20), location="London",
                     species="Fox/badger tick", latin_name="Ixodes canisuga"),
            Sighting(id="c", date=utc(2024, 2, 5), location="Leeds",
                     species="Marsh tick", latin_name="Ixodes apronophorus"),
            Sighting(id="d", date=utc(2023, 6, 1), location="Sheffield",
                     species="Marsh tick", latin_name="Ixodes apronophorus"),
        ])
        session.commit()

        app.dependency_overrides[get_session] = lambda: session
        yield TestClient(app)
        app.dependency_overrides.clear()