import time

import httpx

from ucl.config import settings


class FootballDataClient:
    BASE_URL = "https://api.football-data.org/v4"

    def __init__(self) -> None:
        self.http = httpx.Client(
            base_url=self.BASE_URL,
            headers={"X-Auth-Token": settings.football_data_token},
            timeout=30,
        )

    def champions_league_matches(self, season: int) -> list[dict]:
        resp = self.http.get("/competitions/CL/matches", params={"season": season})
        resp.raise_for_status()
        time.sleep(7)  # stay under the free-tier rate limit
        return resp.json()["matches"]