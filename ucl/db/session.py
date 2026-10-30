from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ucl.config import settings
from ucl.db.models import Base

Path("data").mkdir(exist_ok=True)
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(engine)


def init_db() -> None:
    Base.metadata.create_all(engine)