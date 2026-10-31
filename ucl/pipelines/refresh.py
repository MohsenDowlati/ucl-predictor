from datetime import date

from ucl.db.session import SessionLocal, init_db
from ucl.features import build
from ucl.ingestion.client import FootballDataClient
from ucl.ingestion.historical import upsert_matches
from ucl.models import predict


def current_season(today: date | None = None) -> int:
    today = today or date.today()
    return today.year if today.month >= 7 else today.year - 1


def run() -> None:
    init_db()
    season = current_season()
    print(f"Fetching season {season} from football-data.org...")
    matches = FootballDataClient().champions_league_matches(season)
    with SessionLocal() as session:
        upsert_matches(session, season, matches)
        session.commit()
    build.run()
    predict.run()


if __name__ == "__main__":
    run()