from datetime import datetime

from ucl.db.models import Match, Team
from ucl.db.session import SessionLocal, init_db
from ucl.ingestion.client import FootballDataClient, SeasonNotAvailable


def upsert_matches(session, season: int, raw_matches: list[dict]) -> None:
    for m in raw_matches:
        home, away = m["homeTeam"], m["awayTeam"]
        if home.get("id") is None or away.get("id") is None:
            continue

        for t in (home, away):
            session.merge(Team(id=t["id"], name=t["name"], short_name=t.get("shortName")))

        score = m["score"]
        duration = score.get("duration", "REGULAR")
        regular = score.get("regularTime") or score["fullTime"]
        if duration != "REGULAR" and not score.get("regularTime"):
            print(f"  warning: match {m['id']} ({duration}) has no regularTime; "
                  "its goals may include extra time")

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
                home_goals=regular["home"],
                away_goals=regular["away"],
                duration=duration,
                source="football-data",
            )
        )


def run(first_season: int = 2023, last_season: int = 2026) -> None:
    init_db()
    client = FootballDataClient()
    with SessionLocal() as session:
        for season in range(last_season, first_season - 1, -1):
            print(f"Fetching {season}...")
            try:
                matches = client.champions_league_matches(season)
            except SeasonNotAvailable as e:
                print(f"  skipped -> {e}")
                continue
            upsert_matches(session, season, matches)
            session.commit()
            print(f"  saved {len(matches)} matches")


if __name__ == "__main__":
    run()