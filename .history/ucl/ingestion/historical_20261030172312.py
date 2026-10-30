from datetime import datetime

from ucl.db.models import Match, Team
from ucl.db.session import SessionLocal, init_db
from ucl.ingestion.client import FootballDataClient


def upsert_matches(session, season: int, raw_matches: list[dict]) -> None:
    for m in raw_matches:
        home, away = m["homeTeam"], m["awayTeam"]
        if home.get("id") is None or away.get("id") is None:
            continue

        for t in (home, away):
            session.merge(Team(id=t["id"], name=t["name"], short_name=t.get("shortName")))

        full_time = m["score"]["fullTime"]
        session.merge(
            Match(
                id=m["id"],
                season=season,
                utc_date=datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00")),
                stage=m.get("stage"),
                matchday=m.get("matchday"),
                status=m["status"],
                home_team_id=home["id"],
                away_team_id=away["id"],
                home_goals=full_time["home"],
                away_goals=full_time["away"],
            )
        )


def run(first_season: int = 2018, last_season: int = 2026) -> None:
    init_db()
    client = FootballDataClient()
    with SessionLocal() as session:
        for season in range(first_season, last_season + 1):
            print(f"Fetching {season}...")
            upsert_matches(session, season, client.champions_league_matches(season))
            session.commit()


if __name__ == "__main__":
    run()