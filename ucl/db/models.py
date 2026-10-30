from datetime import datetime, timezone

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


UPCOMING_STATUSES = ("SCHEDULED", "TIMED")


class Base(DeclarativeBase):
    pass


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)  # ID from the API
    name: Mapped[str]
    short_name: Mapped[str | None]


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    season: Mapped[int]
    utc_date: Mapped[datetime]
    stage: Mapped[str | None]
    matchday: Mapped[int | None]
    status: Mapped[str]
    home_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    home_goals: Mapped[int | None]          # score after 90 minutes
    away_goals: Mapped[int | None]
    duration: Mapped[str | None]            # REGULAR / EXTRA_TIME / PENALTY_SHOOTOUT
    source: Mapped[str] = mapped_column(default="football-data")



class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    model_version: Mapped[str]
    p_home: Mapped[float]
    p_draw: Mapped[float]
    p_away: Mapped[float]
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc))