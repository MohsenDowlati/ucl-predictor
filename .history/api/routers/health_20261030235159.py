import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.deps import get_session
from ucl.config import settings

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(session: Session = Depends(get_session)):
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/model/info")
def model_info():
    path = Path("artifacts") / f"metrics_{settings.model_version}.json"
    if not path.exists():
        raise HTTPException(404, "No metrics found for this model version")
    return {"version": settings.model_version, **json.loads(path.read_text())}