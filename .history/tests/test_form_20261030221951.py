import random
from datetime import datetime, timedelta

import pandas as pd
import pytest

from ucl.features.form import (
    DEFAULT_PRIOR_GOALS, DEFAULT_PRIOR_PTS, MAX_REST, compute_form)

COLS = ["home_form_pts", "home_form_gf", "home_form_ga", "home_rest_days",
        "away_form_pts", "away_form_gf", "away_form_ga", "away_rest_days"]


def match(i, day, home, away, hg=None, ag=None, stage="GROUP_STAGE"):
    finished = hg is not None
    return {
        "id": i, "season": 2023,
        "utc_date": datetime(2023, 9, 1) + timedelta(days=day),
        "stage": stage, "status": "FINISHED" if finished else "SCHEDULED",
        "home_team_id": home, "away_team_id": away,
        "home_goals": hg if finished else float("nan"),
        "away_goals": ag if finished else float("nan"),
    }


def random_matches(n=60, seed=0):
    rng = random.Random(seed)
    return pd.DataFrame([
        match(i + 1, 7 * i, *rng.sample(range(1, 7), 2), rng.randint(0, 4), rng.randint(0, 4))
        for i in range(n)
    ])


def test_first_match_uses_priors():
    row = compute_form(pd.DataFrame([match(1, 0, 1, 2, 1, 0)])).iloc[0]
    assert row.home_form_pts == pytest.approx(DEFAULT_PRIOR_PTS)
    assert row.away_form_gf == pytest.approx(DEFAULT_PRIOR_GOALS)
    assert row.home_rest_days == MAX_REST
    assert row.home_n_prior == 0


def test_hand_computed_form_and_rest():
    m = pd.DataFrame([match(1, 0, 1, 2, 2, 0), match(2, 10, 1, 3, 1, 1)])
    second = compute_form(m).iloc[1]
    # after match 1 the league averages are 1.5 points and 1.0 goals per team-match
    assert second.home_form_pts == pytest.approx((3 + 2 * 1.5) / 3)   # 2.0
    assert second.home_form_gf == pytest.approx((2 + 2 * 1.0) / 3)
    assert second.home_form_ga == pytest.approx((0 + 2 * 1.0) / 3)
    assert second.away_form_pts == pytest.approx(1.5)                  # team 3: no history
    assert second.home_rest_days == 10
    assert second.away_rest_days == MAX_REST


def test_is_knockout_flag():
    m = pd.DataFrame([
        match(1, 0, 1, 2, 1, 0, stage="GROUP_STAGE"),
        match(2, 7, 1, 2, 1, 0, stage="LEAGUE_STAGE"),
        match(3, 14, 1, 2, 1, 0, stage="LAST_16"),
    ])
    assert compute_form(m).is_knockout.tolist() == [0, 0, 1]


def test_features_never_depend_on_current_or_future_results():
    matches = random_matches()
    base = compute_form(matches)
    for i in range(len(matches)):
        changed = matches.copy()
        changed.loc[i:, "home_goals"] += 3        # rewrite match i and everything after
        alt = compute_form(changed)
        pd.testing.assert_frame_equal(base.loc[:i, COLS], alt.loc[:i, COLS])


def test_changing_a_result_does_change_later_features():
    # guards against the leakage test passing only because nothing ever changes
    matches = random_matches()
    changed = matches.copy()
    changed.loc[0, "home_goals"] += 3
    assert not compute_form(matches).loc[1:, COLS].equals(compute_form(changed).loc[1:, COLS])


def test_scheduled_matches_get_features_without_changing_form():
    m = pd.DataFrame([match(1, 0, 1, 2, 3, 0), match(2, 20, 1, 3), match(3, 27, 1, 4)])
    f = compute_form(m)
    first, second = f.iloc[1], f.iloc[2]
    assert second.home_form_pts == pytest.approx(first.home_form_pts)   # no result in between
    assert first.home_rest_days == 20 and second.home_rest_days == 7    # dates known in advance