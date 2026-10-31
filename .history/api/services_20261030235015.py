from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import MatchOut, Probabilities, TeamRef
from ucl.config import settings
from ucl.db.models import Match, Prediction, Team


def utc(dt: datetime) -> datetime:
    """Stored timestamps are naive UTC for current fixtures; mark them so JSON ends in Z."""
    return dt.replace(tzinfo=UTC)


def to_probs(p: Prediction) -> Probabilities:
    return Probabilities(home=p.p_home, draw=p.p_draw, away=p.p_away,
                         model_version=p.model_version, created_at=utc(p.created_at))


def build_match_outs(session: Session, matches: list[Match]) -> list[MatchOut]:
    if not matches:
        return []
    team_ids = {t for m in matches for t in (m.home_team_id, m.away_team_id)}
    teams = {t.id: t for t in session.scalars(select(Team).where(Team.id.in_(team_ids)))}

    latest: dict[int, Prediction] = {}
    stmt = (select(Prediction)
            .where(Prediction.match_id.in_([m.id for m in matches]),
                   Prediction.model_version == settings.model_version)
            .order_by(Prediction.id))
    for p in session.scalars(stmt):
        latest[p.match_id] = p              # ordered by id, so the newest wins

    def ref(team_id: int) -> TeamRef:
        t = teams[team_id]
        return TeamRef(id=t.id, name=t.name, short_name=t.short_name)

    return [
        MatchOut(
            id=m.id, season=m.season, kickoff=utc(m.utc_date), stage=m.stage,
            status=m.status, home=ref(m.home_team_id), away=ref(m.away_team_id),
            home_goals=m.home_goals, away_goals=m.away_goals,
            prediction=to_probs(latest[m.id]) if m.id in latest else None,
        )
        for m in matches
    ]