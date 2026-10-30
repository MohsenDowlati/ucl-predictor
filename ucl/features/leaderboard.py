import pandas as pd

from ucl.db.session import engine


def leaderboard(n: int = 15) -> pd.DataFrame:
    h = pd.read_sql(
        "SELECT h.team_id, h.elo_after, h.utc_date, m.season "
        "FROM elo_history h JOIN matches m ON m.id = h.match_id",
        engine, parse_dates=["utc_date"])
    teams = pd.read_sql("SELECT id, name FROM teams", engine)

    last = h.sort_values("utc_date").groupby("team_id").tail(1)   # latest rating per team
    last = last[last.season >= h.season.max() - 1]                # active in last two seasons
    out = last.merge(teams, left_on="team_id", right_on="id")
    out = out.sort_values("elo_after", ascending=False).head(n)
    return out[["name", "elo_after", "utc_date"]].round(1).reset_index(drop=True)


if __name__ == "__main__":
    print(leaderboard().to_string())