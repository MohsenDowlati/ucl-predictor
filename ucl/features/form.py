from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import pandas as pd

WINDOW = 5                 # last N finished matches
PRIOR_WEIGHT = 2.0         # pseudo-matches of an "average team" blended into each average
MAX_REST = 30              # days; also the value for a team's first match
GROUP_STAGES = {"GROUP_STAGE", "LEAGUE_STAGE"}
DEFAULT_PRIOR_PTS = 1.3    # used only before any match has been seen
DEFAULT_PRIOR_GOALS = 1.4


@dataclass
class TeamState:
    recent: deque = field(default_factory=lambda: deque(maxlen=WINDOW)) 
    last_date: pd.Timestamp | None = None
    played: int = 0


def shrunk(values: list[float], prior: float) -> float:
    return (sum(values) + PRIOR_WEIGHT * prior) / (len(values) + PRIOR_WEIGHT)


def team_features(state: TeamState, day: pd.Timestamp,
                  prior_pts: float, prior_goals: float) -> dict:
    pts = [p for p, _, _ in state.recent]
    gf = [g for _, g, _ in state.recent]
    ga = [a for _, _, a in state.recent]
    rest = MAX_REST if state.last_date is None else min((day - state.last_date).days, MAX_REST)
    return {
        "form_pts": shrunk(pts, prior_pts),
        "form_gf": shrunk(gf, prior_goals),
        "form_ga": shrunk(ga, prior_goals),
        "rest_days": rest,
        "n_prior": state.played,
    }


def compute_form(matches: pd.DataFrame) -> pd.DataFrame:
    """matches needs: id, utc_date, stage, status, home_team_id, away_team_id,
    home_goals, away_goals. Returns one row per match, keyed by match_id."""
    df = matches.sort_values(["utc_date", "id"]).reset_index(drop=True)
    teams: dict[int, TeamState] = {}
    tot_pts = tot_goals = tot_n = 0.0     # running league averages, past matches only
    rows = []

    for r in df.itertuples(index=False):
        day = r.utc_date.normalize()
        home = teams.setdefault(r.home_team_id, TeamState())
        away = teams.setdefault(r.away_team_id, TeamState())
        prior_pts = tot_pts / tot_n if tot_n else DEFAULT_PRIOR_PTS
        prior_goals = tot_goals / tot_n if tot_n else DEFAULT_PRIOR_GOALS

        h = team_features(home, day, prior_pts, prior_goals)
        a = team_features(away, day, prior_pts, prior_goals)
        row = {
            "match_id": r.id,
            "is_knockout": int(isinstance(r.stage, str) and r.stage not in GROUP_STAGES),
        }
        row.update({f"home_{k}": v for k, v in h.items()})
        row.update({f"away_{k}": v for k, v in a.items()})
        for k in ("form_pts", "form_gf", "form_ga", "rest_days"):
            row[f"{k}_diff"] = h[k] - a[k]
        rows.append(row)

        if r.status == "FINISHED" and pd.notna(r.home_goals) and pd.notna(r.away_goals):
            hg, ag = int(r.home_goals), int(r.away_goals)
            hp, ap = (3, 0) if hg > ag else (0, 3) if hg < ag else (1, 1)
            home.recent.append((hp, hg, ag))
            away.recent.append((ap, ag, hg))
            home.played += 1
            away.played += 1
            tot_pts += hp + ap
            tot_goals += hg + ag
            tot_n += 2

        home.last_date = away.last_date = day

    return pd.DataFrame(rows)