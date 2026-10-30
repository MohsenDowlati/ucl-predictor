from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class EloConfig:
    k: float = 30.0               
    home_advantage: float = 60.0   
    initial: float = 1500.0        
    season_retain: float = 0.8    


def expected_score(r_home: float, r_away: float, home_advantage: float = 0.0) -> float:
    """Expected points for the home side: 1 = win, 0.5 = draw, 0 = loss."""
    return 1.0 / (1.0 + 10 ** (-(r_home + home_advantage - r_away) / 400.0))


def goal_multiplier(goal_diff: int) -> float:
    """Bigger wins move ratings more."""
    n = abs(goal_diff)
    if n <= 1:
        return 1.0
    if n == 2:
        return 1.5
    return (11 + n) / 8


class Elo:
    def __init__(self, cfg: EloConfig = EloConfig()):
        self.cfg = cfg
        self.ratings: dict[int, float] = {}

    def rating(self, team_id: int) -> float:
        return self.ratings.get(team_id, self.cfg.initial)

    def new_season(self) -> None:
        c = self.cfg
        self.ratings = {
            t: c.initial + c.season_retain * (r - c.initial)
            for t, r in self.ratings.items()
        }

    def update(self, home_id: int, away_id: int, home_goals: int, away_goals: int,
               neutral: bool = False) -> tuple[float, float]:
        r_home, r_away = self.rating(home_id), self.rating(away_id)
        hfa = 0.0 if neutral else self.cfg.home_advantage
        expected = expected_score(r_home, r_away, hfa)
        actual = 1.0 if home_goals > away_goals else 0.5 if home_goals == away_goals else 0.0
        delta = self.cfg.k * goal_multiplier(home_goals - away_goals) * (actual - expected)
        self.ratings[home_id] = r_home + delta
        self.ratings[away_id] = r_away - delta      # zero-sum
        return self.ratings[home_id], self.ratings[away_id]


@dataclass
class EloResult:
    features: pd.DataFrame           
    history: pd.DataFrame            
    ratings: dict[int, float]        


def compute_elo(matches: pd.DataFrame, cfg: EloConfig = EloConfig()) -> EloResult:
    """matches needs: id, season, utc_date, stage, status, home_team_id,
    away_team_id, home_goals, away_goals."""
    df = matches.sort_values(["utc_date", "id"]).reset_index(drop=True)
    elo = Elo(cfg)
    features: list[dict] = []
    history: list[dict] = []
    prev_season = None

    for r in df.itertuples(index=False):
        if prev_season is not None:
            if r.season < prev_season:
                raise ValueError(f"Match {r.id}: season goes backwards in time")
            if r.season > prev_season:
                elo.new_season()
        prev_season = r.season

        neutral = r.stage == "FINAL"
        r_home, r_away = elo.rating(r.home_team_id), elo.rating(r.away_team_id)
        expected = expected_score(r_home, r_away, 0.0 if neutral else cfg.home_advantage)

        finished = (r.status == "FINISHED"
                    and pd.notna(r.home_goals) and pd.notna(r.away_goals))
        result = None
        if finished:
            hg, ag = int(r.home_goals), int(r.away_goals)
            result = "H" if hg > ag else "A" if hg < ag else "D"

        features.append({
            "match_id": r.id, "season": r.season, "utc_date": r.utc_date,
            "stage": r.stage, "status": r.status,
            "home_team_id": r.home_team_id, "away_team_id": r.away_team_id,
            "elo_home": r_home, "elo_away": r_away, "elo_diff": r_home - r_away,
            "neutral": int(neutral), "elo_expected_home": expected, "result": result,
        })
        
        if finished:
            after_home, after_away = elo.update(
                r.home_team_id, r.away_team_id, hg, ag, neutral)
            history.append({"match_id": r.id, "team_id": r.home_team_id,
                            "utc_date": r.utc_date,
                            "elo_before": r_home, "elo_after": after_home})
            history.append({"match_id": r.id, "team_id": r.away_team_id,
                            "utc_date": r.utc_date,
                            "elo_before": r_away, "elo_after": after_away})

    return EloResult(
        features=pd.DataFrame(features),
        history=pd.DataFrame(history, columns=[
            "match_id", "team_id", "utc_date", "elo_before", "elo_after"]),
        ratings=dict(elo.ratings),
    )