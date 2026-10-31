import argparse
import hashlib
from datetime import date

from sqlalchemy import text

from ucl.db.session import SessionLocal, engine, init_db
from ucl.features import build
from ucl.ingestion.client import FootballDataClient
from ucl.ingestion.historical import upsert_matches
from ucl.models import predict


def current_season(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def fingerprint(db_engine, season: int) -> str:
    """Hash of everything a rebuild depends on: status, score, kickoff time."""
    with db_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT id, status, home_goals, away_goals, utc_date "
                 "FROM matches WHERE season = :s ORDER BY id"), {"s": season}).all()
    return hashlib.sha256(repr([tuple(r) for r in rows]).encode()).hexdigest()


def run(force: bool = False, verbose: bool = False) -> bool:
    """Fetch the current season. Rebuild ratings, features and predictions only if
    something changed (or force=True). Returns True when a rebuild happened."""
    init_db()
    season = current_season()
    before = fingerprint(engine, season)

    client = FootballDataClient()
    try:
        matches = client.champions_league_matches(season)
    finally:
        client.http.close()
    with SessionLocal() as session:
        upsert_matches(session, season, matches)
        session.commit()

    if not force and fingerprint(engine, season) == before:
        return False
    build.run(verbose=verbose)
    predict.run()
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="rebuild even if nothing changed")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    print("updated" if run(force=args.force, verbose=args.verbose) else "no changes")