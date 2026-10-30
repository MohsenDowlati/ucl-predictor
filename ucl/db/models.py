from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)  # ID from the API
    name: Mapped[str]
    short_name: Mapped[str | None]


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)  # ID from the API
    season: Mapped[int]                                # start year, e.g. 2024
    utc_date: Mapped[datetime]
    stage: Mapped[str | None]
    matchday: Mapped[int | None]
    status: Mapped[str]                                # SCHEDULED, FINISHED, ...
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_goals: Mapped[int | None]
    away_goals: Mapped[int | None]