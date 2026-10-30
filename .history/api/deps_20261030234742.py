from collections.abc import Iterator

from sqlalchemy.orm import Session

from ucl.db.session import SessionLocal


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session