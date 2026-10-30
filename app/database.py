from pathlib import Path

from sqlmodel import SQLModel, create_engine

DB_PATH = Path("data/ticks.db")
engine = create_engine(f"sqlite:///{DB_PATH}")


def create_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    SQLModel.metadata.create_all(engine)