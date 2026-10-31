from datetime import datetime, timedelta

import pandas as pd
import pytest

from ucl.monitoring.metrics import (
    MIN_MATCHES, clipped_share, climatology_before, evaluate_live,
    missing_predictions, scored_predictions, stale_matches)

T0 = datetime(2026, 10, 1, 19)
NOW = datetime(2026, 11, 5, 12, 0)
NAN = float("nan")


def matches_frame(rows):
    return pd.DataFrame(rows, columns=["id", "season", "utc_date", "status",
                                       "home_goals", "away_goals"])


def preds_frame(rows):
    return pd.DataFrame(rows, columns=["pred_id", "match_id", "p_home", "p_draw",
                                       "p_away", "created_at"])


def scored_frame(n, p, results):
    return pd.DataFrame({
        "p_home": [p[0]] * n, "p_draw": [p[1]] * n, "p_away": [p[2]] * n,
        "base_H": [0.45] * n, "base_D": [0.25] * n, "base_A": [0.30] * n,
        "result": results,
    })


def test_scored_predictions_uses_last_prekickoff_prediction_only():
    matches = matches_frame([
        (1, 2026, T0, "FINISHED", 2, 0),
        (2, 2026, T0 + timedelta(days=1), "FINISHED", 0, 0),
        (3, 2026, T0 + timedelta(days=2), "SCHEDULED", NAN, NAN),
    ])
    preds = preds_frame([
        (1, 1, 0.5, 0.3, 0.2, T0 - timedelta(days=3)),
        (2, 1, 0.6, 0.2, 0.2, T0 - timedelta(days=1)),    # newest before kickoff: used
        (3, 1, 0.1, 0.1, 0.8, T0 + timedelta(hours=3)),   # written after kickoff: ignored
        (4, 2, 0.3, 0.4, 0.3, T0),
        (5, 3, 0.4, 0.3, 0.3, T0),                        # match not finished: not scored
    ])
    out = scored_predictions(preds, matches)
    assert out.match_id.tolist() == [1, 2]
    assert out.p_home.tolist() == [0.6, 0.3]
    assert out.result.tolist() == ["H", "D"]


def test_scored_predictions_with_nothing_to_score():
    matches = matches_frame([(1, 2026, T0, "SCHEDULED", NAN, NAN)])
    assert scored_predictions(preds_frame([]), matches).empty
    assert evaluate_live(pd.DataFrame())["status"] == "NO_DATA"


def test_baseline_uses_only_strictly_earlier_days():
    fin = matches_frame([
        (1, 2026, T0, "FINISHED", 1, 0),                                  # H, first day
        (2, 2026, T0 + timedelta(days=1), "FINISHED", 0, 0),              # D
        (3, 2026, T0 + timedelta(days=1, hours=2), "FINISHED", 0, 2),     # A, same day as 2
        (4, 2026, T0 + timedelta(days=2), "FINISHED", 1, 1),
    ])
    out = climatology_before(fin).set_index("match_id")
    cols = ["base_H", "base_D", "base_A"]
    assert out.loc[1, cols].isna().all()
    assert out.loc[2, cols].tolist() == pytest.approx([1, 0, 0])
    assert out.loc[3, cols].tolist() == pytest.approx([1, 0, 0])      # must not see match 2
    assert out.loc[4, cols].tolist() == pytest.approx([1 / 3] * 3)


def test_too_few_matches_gives_no_verdict():
    s = evaluate_live(scored_frame(10, (0.6, 0.2, 0.2), ["H"] * 10))
    assert s["n"] == 10 and s["status"] == "TOO_FEW" and "diff" not in s


def test_model_better_than_baseline_is_ok():
    results = ["H"] * 36 + ["D"] * 12 + ["A"] * 12
    out = evaluate_live(scored_frame(60, (0.6, 0.2, 0.2), results))
    assert len(results) >= MIN_MATCHES
    assert out["status"] == "OK" and out["diff"] < 0


def test_confidently_wrong_model_is_flagged():
    results = ["H"] * 40 + ["D"] * 10 + ["A"] * 10
    out = evaluate_live(scored_frame(60, (0.05, 0.05, 0.90), results))
    assert out["status"] == "WARN" and out["ci_low"] > 0


def test_stale_matches_flags_only_overdue_active_statuses():
    m = matches_frame([
        (1, 2026, NOW - timedelta(hours=5), "SCHEDULED", NAN, NAN),   # overdue
        (2, 2026, NOW - timedelta(hours=1), "IN_PLAY", NAN, NAN),     # live: fine
        (3, 2026, NOW - timedelta(hours=9), "FINISHED", 1, 0),        # finished: fine
        (4, 2026, NOW - timedelta(hours=9), "POSTPONED", NAN, NAN),   # ignored
    ])
    assert stale_matches(m, NOW).id.tolist() == [1]


def test_missing_predictions_only_in_the_coming_window():
    m = matches_frame([
        (1, 2026, NOW + timedelta(days=2), "SCHEDULED", NAN, NAN),    # has a prediction
        (2, 2026, NOW + timedelta(days=3), "TIMED", NAN, NAN),        # missing
        (3, 2026, NOW + timedelta(days=40), "SCHEDULED", NAN, NAN),   # too far ahead
        (4, 2026, NOW - timedelta(days=1), "FINISHED", 1, 0),         # not upcoming
    ])
    assert missing_predictions(m, [1], NOW).id.tolist() == [2]


def test_clipped_share():
    f = pd.DataFrame({"elo_diff": [-400.0, 0.0, 10.0, 500.0]})
    assert clipped_share(f, {"elo_diff": (-200.0, 200.0)}) == {"elo_diff": 0.5}