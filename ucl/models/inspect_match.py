import sys

import pandas as pd

from ucl.db.session import engine
from ucl.models.data import FULL_FEATURES, load_features, split


def run(home_frag: str, away_frag: str) -> None:
    f = load_features()
    teams = pd.read_sql("SELECT id, name FROM teams", engine)

    def team_id(frag: str) -> int:
        hit = teams[teams.name.str.contains(frag, case=False, regex=False)]
        if len(hit) != 1:
            raise SystemExit(f"{frag!r} matched {hit.name.tolist()} - use a more specific name")
        return int(hit.id.iloc[0])

    h, a = team_id(home_frag), team_id(away_frag)
    upcoming = f[(f.home_team_id == h) & (f.away_team_id == a) & f.result.isna()]
    if upcoming.empty:
        raise SystemExit("No upcoming match with that home/away order")
    row = upcoming.sort_values("utc_date").iloc[0]

    train, val, _ = split(f)
    fit = pd.concat([train, val])

    show = ["utc_date", "elo_home", "elo_away", "elo_expected_home",
            "home_n_prior", "away_n_prior"] + FULL_FEATURES
    print(row[show].to_string())

    print("\nThis match vs the data the model was fit on")
    for c in FULL_FEATURES:
        if c in ("neutral", "is_knockout"):
            continue
        p5, p50, p95 = fit[c].quantile([0.05, 0.5, 0.95]).round(2)
        share = (fit[c].abs() >= abs(row[c])).mean()
        print(f"  {c:16} this match {row[c]:8.2f} | train p5 {p5:8.2f}  p50 {p50:8.2f}  "
              f"p95 {p95:8.2f} | as extreme or more: {share:.1%}")


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])