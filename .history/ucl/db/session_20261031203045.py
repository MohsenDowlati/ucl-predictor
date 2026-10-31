from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from ucl.config import settings
from ucl.db.models import Base

Path("data").mkdir(exist_ok=True)
engine = create_engine(settings.database_url)

if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")    
        cur.execute("PRAGMA busy_timeout=5000")  
        cur.close()


SessionLocal = sessionmaker(engine)


def init_db() -> None:
    Base.metadata.create_all(engine)