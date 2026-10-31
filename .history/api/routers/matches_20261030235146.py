from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.deps import get_session
from api.schemas import MatchDetail, MatchOut
from api.services import build_match_outs, to_probs
from ucl.config import settings
from ucl.db.models import UPCOMING_STATUSES, Match, Prediction

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_model=list[MatchOut])
def list_matches(
    status: Literal["upcoming", "finished", "all"] = "upcoming",
    season: int | None = None,
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    stmt = select(Match)
    if status == "upcoming":
        stmt = stmt.where(Match.status.in_(UPCOMING_STATUSES)).order_by(Match.utc_date, Match.id)
    elif status == "finished":
        stmt = stmt.where(Match.status == "FINISHED").order_by(
            Match.utc_date.desc(), Match.id.desc())
    else:
        stmt = stmt.order_by(Match.utc_date, Match.id)
    if season is not None:
        stmt = stmt.where(Match.season == season)
    return build_match_outs(session, list(session.scalars(stmt.limit(limit))))


@router.get("/{match_id}", response_model=MatchDetail)
def match_detail(match_id: int, session: Session = Depends(get_session)):
    match = session.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "Match not found")
    base = build_match_outs(session, [match])[0]
    history = session.scalars(
        select(Prediction)
        .where(Prediction.match_id == match_id,
               Prediction.model_version == settings.model_version)
        .order_by(Prediction.id))
    return MatchDetail(**base.model_dump(), prediction_history=[to_probs(p) for p in history])