from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from api.deps import get_session
from api.schemas import EloPoint, MatchOut, TeamDetail, TeamOut
from api.services import build_match_outs
from ucl.db.models import UPCOMING_STATUSES, Match, Team

router = APIRouter(prefix="/teams", tags=["teams"])

LATEST_ELO_SQL = text("""
    SELECT team_id, elo_after FROM (
        SELECT team_id, elo_after,
               ROW_NUMBER() OVER (PARTITION BY team_id
                                  ORDER BY utc_date DESC, match_id DESC) AS rn
        FROM elo_history
    ) AS ranked WHERE rn = 1
""")


def team_matches(session: Session, team_id: int, upcoming: bool, limit: int) -> list[MatchOut]:
    involved = or_(Match.home_team_id == team_id, Match.away_team_id == team_id)
    if upcoming:
        stmt = select(Match).where(involved, Match.status.in_(UPCOMING_STATUSES)).order_by(
            Match.utc_date, Match.id)
    else:
        stmt = select(Match).where(involved, Match.status == "FINISHED").order_by(
            Match.utc_date.desc(), Match.id.desc())
    return build_match_outs(session, list(session.scalars(stmt.limit(limit))))


@router.get("", response_model=list[TeamOut])
def list_teams(active_only: bool = True, session: Session = Depends(get_session)):
    elo = {r.team_id: r.elo_after for r in session.execute(LATEST_ELO_SQL)}
    teams = list(session.scalars(select(Team)))

    latest = session.scalar(select(func.max(Match.season)))
    if active_only and latest is not None:
        recent = Match.season >= latest - 1
        active = set(session.scalars(select(Match.home_team_id).where(recent)))
        active |= set(session.scalars(select(Match.away_team_id).where(recent)))
        teams = [t for t in teams if t.id in active]

    out = [TeamOut(id=t.id, name=t.name, short_name=t.short_name, elo=elo.get(t.id))
           for t in teams]
    return sorted(out, key=lambda t: (t.elo is None, -(t.elo or 0.0)))


@router.get("/{team_id}", response_model=TeamDetail)
def team_detail(team_id: int, session: Session = Depends(get_session)):
    team = session.get(Team, team_id)
    if team is None:
        raise HTTPException(404, "Team not found")
    rows = session.execute(
        text("SELECT match_id, utc_date, elo_after FROM elo_history "
             "WHERE team_id = :t ORDER BY utc_date, match_id"), {"t": team_id}).all()
    history = [EloPoint(date=r.utc_date, elo=r.elo_after, match_id=r.match_id) for r in rows]
    return TeamDetail(
        id=team.id, name=team.name, short_name=team.short_name,
        elo=history[-1].elo if history else None,
        elo_history=history,
        recent_matches=team_matches(session, team_id, upcoming=False, limit=10),
        upcoming_matches=team_matches(session, team_id, upcoming=True, limit=5),
    )