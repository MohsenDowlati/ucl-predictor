import time

import httpx

from ucl.config import settings


class SeasonNotAvailable(Exception):
    pass


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
        time.sleep(7)  # free tier rate limit
        if resp.status_code == 403:
            raise SeasonNotAvailable(f"{season}: {resp.text}")
        resp.raise_for_status()
        return resp.json()["matches"]