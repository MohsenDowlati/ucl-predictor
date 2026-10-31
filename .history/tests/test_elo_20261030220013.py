import random
from datetime import datetime, timedelta

import pandas as pd
import pytest

from ucl.features.elo import (
    Elo,
    EloConfig,
    compute_elo,
    expected_score,
    goal_multiplier,
)

FEATURE_COLS = ["elo_home", "elo_away", "elo_expected_home"]


def make_matches(n: int = 60, seed: int = 0) -> pd.DataFrame:
    rng = random.Random(seed)
    start = datetime(2023, 9, 1)
    rows = []
    for i in range(n):
        home, away = rng.sample(range(1, 7), 2)
        rows.append({
            "id": i + 1,
            "season": 2023 if i < n // 2 else 2024,
            "utc_date": start + timedelta(days=7 * i),
            "stage": "GROUP_STAGE",
            "status": "FINISHED",
            "home_team_id": home,
            "away_team_id": away,
            "home_goals": rng.randint(0, 4),
            "away_goals": rng.randint(0, 4),
        })
    return pd.DataFrame(rows)


def test_expected_score_is_half_for_equal_teams():
    assert expected_score(1500, 1500) == pytest.approx(0.5)
    assert expected_score(1500, 1500, home_advantage=60) > 0.5


def test_goal_multiplier():
    assert goal_multiplier(0) == 1 and goal_multiplier(-1) == 1
    assert goal_multiplier(2) == 1.5
    assert goal_multiplier(-4) == pytest.approx(15 / 8)


def test_update_is_zero_sum():
    elo = Elo()
    before = elo.rating(1) + elo.rating(2)
    elo.update(1, 2, 3, 0)
    assert elo.rating(1) + elo.rating(2) == pytest.approx(before)
    assert elo.rating(1) > 1500 > elo.rating(2)


def test_new_season_shrinks_toward_initial():
    elo = Elo(EloConfig(season_retain=0.5))
    elo.ratings = {1: 1700.0, 2: 1300.0}
    elo.new_season()
    assert elo.ratings == {1: 1600.0, 2: 1400.0}


def test_features_never_depend_on_current_or_future_results():
    matches = make_matches()
    base = compute_elo(matches).features
    for i in range(len(matches)):
        changed = matches.copy()
        changed.loc[i:, "home_goals"] += 3        
        alt = compute_elo(changed).features
        pd.testing.assert_frame_equal(
            base.loc[:i, FEATURE_COLS], alt.loc[:i, FEATURE_COLS])


def test_changing_a_result_does_change_later_features():
    matches = make_matches()
    changed = matches.copy()
    changed.loc[0, "home_goals"] += 3
    base = compute_elo(matches).features
    alt = compute_elo(changed).features
    assert not base.loc[1:, "elo_home"].equals(alt.loc[1:, "elo_home"])


def test_unplayed_matches_get_features_but_do_not_move_ratings():
    matches = make_matches()
    upcoming = pd.DataFrame([{
        "id": 999, "season": 2024, "utc_date": datetime(2030, 1, 1),
        "stage": "GROUP_STAGE", "status": "SCHEDULED",
        "home_team_id": 1, "away_team_id": 2,
        "home_goals": float("nan"), "away_goals": float("nan"),
    }])
    base = compute_elo(matches)
    with_upcoming = compute_elo(pd.concat([matches, upcoming], ignore_index=True))

    assert with_upcoming.ratings == base.ratings
    row = with_upcoming.features.iloc[-1]
    assert row.match_id == 999 and pd.isna(row.result)
    assert row.elo_home == pytest.approx(base.ratings[1])