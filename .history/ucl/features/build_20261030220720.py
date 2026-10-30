import pandas as pd

from ucl.db.session import engine
from ucl.features.elo import EloResult, compute_elo

WARMUP_SEASONS = 2 


def load_matches() -> pd.DataFrame:
    return pd.read_sql(
        "SELECT id, season, utc_date, stage, status, home_team_id, away_team_id, "
        "home_goals, away_goals FROM matches",
        engine, parse_dates=["utc_date"])


def report(result: EloResult) -> None:
    f = result.features
    teams = pd.read_sql("SELECT id, name FROM teams", engine).set_index("id")["name"]

    latest = f.season.max()
    recent = f[f.season >= latest - 1]
    recent_ids = set(recent[["home_team_id", "away_team_id"]].to_numpy().ravel())
    top = sorted(((r, t) for t, r in result.ratings.items() if t in recent_ids),
                 reverse=True)[:15]
    print("\nTop 15 current ratings (teams active in the last two seasons)")
    for r, t in top:
        print(f"  {r:7.1f}  {teams[t]}")

    done = f[f.result.notna() & (f.season >= f.season.min() + WARMUP_SEASONS)].copy()
    done["score"] = done.result.map({"H": 1.0, "D": 0.5, "A": 0.0})
    done["bin"] = pd.cut(done.elo_expected_home, [0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0])
    print("\nCalibration: Elo's expected score vs what actually happened")
    print(done.groupby("bin", observed=True).agg(
        n=("score", "size"),
        predicted=("elo_expected_home", "mean"),
        actual=("score", "mean")).round(3))

    decisive = done[done.result != "D"]
    fav = (decisive.elo_expected_home > 0.5) == (decisive.result == "H")
    print(f"\nHigher-rated side wins {fav.mean():.1%} of {len(decisive)} decisive matches")


def run() -> None:
    result = compute_elo(load_matches())
    result.features.to_sql("match_features", engine, if_exists="replace", index=False)
    result.history.to_sql("elo_history", engine, if_exists="replace", index=False)
    upcoming = int(result.features.result.isna().sum())
    print(f"{len(result.features)} feature rows ({upcoming} not yet played), "
          f"{len(result.history)} rating-history rows")
    report(result)


if __name__ == "__main__":
    run()