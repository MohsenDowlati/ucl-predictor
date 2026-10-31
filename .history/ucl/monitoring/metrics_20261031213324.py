from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from ucl.db.models import UPCOMING_STATUSES
from ucl.models.evaluate import CLASSES, brier, paired_bootstrap, per_match_log_loss

MIN_MATCHES = 30                
ROLLING = 50                   
UPCOMING_DAYS = 14
STALE_AFTER = timedelta(hours=4)
CLIP_ALERT = 0.10               
ACTIVE_STATUSES = ("SCHEDULED", "TIMED", "IN_PLAY", "PAUSED")
BASE_COLS = ["base_H", "base_D", "base_A"]


def climatology_before(finished: pd.DataFrame) -> pd.DataFrame:
    """Home/draw/away rates over finished matches on strictly earlier days
    (a leak-free baseline). The first day has no history, so its rows are NaN."""
    f = finished.copy()
    f["day"] = f.utc_date.dt.normalize()
    f["result"] = np.where(f.home_goals > f.away_goals, "H",
                           np.where(f.home_goals < f.away_goals, "A", "D"))
    daily = pd.crosstab(f["day"], f["result"]).reindex(columns=CLASSES, fill_value=0)
    cum = daily.sort_index().cumsum().shift(1)       # shift: today's results don't count
    rates = cum.div(cum.sum(axis=1), axis=0)
    rates.columns = BASE_COLS
    out = f[["id", "day"]].merge(rates, left_on="day", right_index=True, how="left")
    return out.drop(columns="day").rename(columns={"id": "match_id"})


def scored_predictions(preds: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    """One row per finished match: its last pre-kickoff prediction, the result,
    and the base-rate baseline.

    preds:   pred_id, match_id, p_home, p_draw, p_away, created_at
    matches: id, season, utc_date, status, home_goals, away_goals"""
    finished = matches[(matches.status == "FINISHED")
                       & matches.home_goals.notna() & matches.away_goals.notna()]
    if preds.empty or finished.empty:
        return pd.DataFrame()

    m = preds.merge(
        finished[["id", "season", "utc_date", "home_goals", "away_goals"]],
        left_on="match_id", right_on="id")
    m = m[m.created_at <= m.utc_date]                # ignore anything written after kickoff
    m = m.sort_values(["match_id", "created_at", "pred_id"]).groupby("match_id").tail(1)
    m = m.assign(result=np.where(m.home_goals > m.away_goals, "H",
                                 np.where(m.home_goals < m.away_goals, "A", "D")))
    m = m.merge(climatology_before(finished), on="match_id", how="left")
    m[BASE_COLS] = m[BASE_COLS].fillna(1 / 3)
    return m.sort_values(["utc_date", "match_id"]).reset_index(drop=True)


def evaluate_live(scored: pd.DataFrame) -> dict:
    n = len(scored)
    if n == 0:
        return {"n": 0, "status": "NO_DATA"}

    y = scored.result
    model = scored[["p_home", "p_draw", "p_away"]].to_numpy()
    base = scored[BASE_COLS].to_numpy()
    ll_model, ll_base = per_match_log_loss(y, model), per_match_log_loss(y, base)

    out = {
        "n": n,
        "model_log_loss": float(ll_model.mean()),
        "base_log_loss": float(ll_base.mean()),
        "model_brier": brier(y, model),
        "base_brier": brier(y, base),
        "accuracy": float((np.array(CLASSES)[model.argmax(axis=1)] == y.to_numpy()).mean()),
        "recent_n": min(n, ROLLING),
        "recent_model_log_loss": float(ll_model[-ROLLING:].mean()),
        "recent_base_log_loss": float(ll_base[-ROLLING:].mean()),
        "mean_pred": {c: float(v) for c, v in zip(CLASSES, model.mean(axis=0))},
        "actual": {c: float((y == c).mean()) for c in CLASSES},
    }
    if n < MIN_MATCHES:
        out["status"] = "TOO_FEW"
        return out

    diff, lo, hi = paired_bootstrap(ll_model, ll_base)    # model minus baseline; negative = good
    out.update(diff=diff, ci_low=lo, ci_high=hi)
    out["status"] = "WARN" if lo > 0 else ("WATCH" if diff > 0 else "OK")
    return out


def stale_matches(matches: pd.DataFrame, now: datetime) -> pd.DataFrame:
    """Active-status matches long past kickoff: the data has stopped updating.
    Postponed and cancelled matches are deliberately ignored."""
    return matches[matches.status.isin(ACTIVE_STATUSES)
                   & (matches.utc_date < now - STALE_AFTER)]


def missing_predictions(matches: pd.DataFrame, predicted_ids, now: datetime) -> pd.DataFrame:
    upcoming = matches[matches.status.isin(UPCOMING_STATUSES)
                       & (matches.utc_date >= now)
                       & (matches.utc_date <= now + timedelta(days=UPCOMING_DAYS))]
    return upcoming[~upcoming.id.isin(set(predicted_ids))]


def clipped_share(features: pd.DataFrame, bounds: dict[str, tuple[float, float]]) -> dict[str, float]:
    """Share of rows outside the range the model was trained on, per clipped feature."""
    return {c: float(((features[c] < lo) | (features[c] > hi)).mean())
            for c, (lo, hi) in bounds.items()}