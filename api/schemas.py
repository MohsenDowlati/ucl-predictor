from datetime import datetime

from pydantic import BaseModel


class TeamRef(BaseModel):
    id: int
    name: str
    short_name: str | None


class Probabilities(BaseModel):
    home: float
    draw: float
    away: float
    model_version: str
    created_at: datetime


class MatchOut(BaseModel):
    id: int
    season: int
    kickoff: datetime
    stage: str | None
    status: str
    home: TeamRef
    away: TeamRef
    home_goals: int | None
    away_goals: int | None
    prediction: Probabilities | None


class MatchDetail(MatchOut):
    prediction_history: list[Probabilities]


class TeamOut(BaseModel):
    id: int
    name: str
    short_name: str | None
    elo: float | None


class EloPoint(BaseModel):
    date: datetime
    elo: float
    match_id: int


class TeamDetail(TeamOut):
    elo_history: list[EloPoint]
    recent_matches: list[MatchOut]
    upcoming_matches: list[MatchOut]