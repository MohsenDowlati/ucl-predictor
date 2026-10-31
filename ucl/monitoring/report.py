import argparse
import sys
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import text

from ucl.config import settings
from ucl.db.models import UPCOMING_STATUSES
from ucl.db.session import engine
from ucl.models.evaluate import CLASSES
from ucl.models.predict import load_artifact
from ucl.monitoring import metrics

Check = tuple[str, str]      # (level, message); levels: OK, INFO, WATCH, WARN


def fmt_rates(d: dict[str, float]) -> str:
    return " / ".join(f"{c} {d[c]:.0%}" for c in CLASSES)


def performance_checks(perf: dict) -> list[Check]:
    status = perf["status"]
    if status == "NO_DATA":
        return [("INFO", "Live performance: no finished match has a stored pre-match "
                         "prediction yet.")]

    level = status if status in ("OK", "WATCH", "WARN") else "INFO"
    head = (f"Live performance: {perf['n']} matches scored. Log loss "
            f"{perf['model_log_loss']:.3f} vs {perf['base_log_loss']:.3f} for the "
            f"base-rate baseline (lower is better).")
    if status == "TOO_FEW":
        head += f" Need {metrics.MIN_MATCHES} matches before judging."
    else:
        head += (f" Difference {perf['diff']:+.3f} "
                 f"(95% CI {perf['ci_low']:+.3f} to {perf['ci_high']:+.3f}); "
                 "negative favours the model.")
    return [
        (level, head),
        ("INFO", f"  last {perf['recent_n']}: log loss {perf['recent_model_log_loss']:.3f} "
                 f"vs {perf['recent_base_log_loss']:.3f}; Brier {perf['model_brier']:.3f} "
                 f"vs {perf['base_brier']:.3f}; accuracy {perf['accuracy']:.1%}"),
        ("INFO", f"  average predicted {fmt_rates(perf['mean_pred'])} "
                 f"vs actual {fmt_rates(perf['actual'])}"),
    ]


def run_checks(version: str | None = None) -> list[Check]:
    version = version or settings.model_version
    now = datetime.now(timezone.utc).replace(tzinfo=None)     # the DB stores naive UTC

    matches = pd.read_sql(
        "SELECT id, season, utc_date, status, home_goals, away_goals FROM matches",
        engine, parse_dates=["utc_date"])
    preds = pd.read_sql(
        text("SELECT id AS pred_id, match_id, p_home, p_draw, p_away, created_at "
             "FROM predictions WHERE model_version = :v"),
        engine, params={"v": version}, parse_dates=["created_at"])

    checks = performance_checks(
        metrics.evaluate_live(metrics.scored_predictions(preds, matches)))

    stale = metrics.stale_matches(matches, now)
    if len(stale):
        ids = ", ".join(str(i) for i in stale.id.head(5))
        checks.append(("WARN", f"Data freshness: {len(stale)} match(es) more than "
                               f"{metrics.STALE_AFTER.seconds // 3600} hours past kickoff but "
                               f"not finished (ids {ids}). Is the API still updating?"))
    else:
        checks.append(("OK", "Data freshness: no overdue matches."))

    missing = metrics.missing_predictions(matches, preds.match_id, now)
    if len(missing):
        ids = ", ".join(str(i) for i in missing.id.head(5))
        checks.append(("WARN", f"Prediction coverage: {len(missing)} match(es) in the next "
                               f"{metrics.UPCOMING_DAYS} days have no {version} prediction "
                               f"(ids {ids}). Run ucl.models.predict."))
    else:
        checks.append(("OK", f"Prediction coverage: every match in the next "
                             f"{metrics.UPCOMING_DAYS} days has a {version} prediction."))

    try:
        artifact = load_artifact(version)
    except SystemExit as exc:
        checks.append(("WARN", f"Input range: model file missing ({exc})."))
        return checks

    bounds = getattr(artifact["model"][0], "bounds_", None)
    feats = pd.read_sql("SELECT * FROM match_features WHERE result IS NULL", engine)
    feats = feats[feats.status.isin(UPCOMING_STATUSES)]
    if not bounds or feats.empty:
        checks.append(("INFO", "Input range: nothing to check."))
    else:
        shares = metrics.clipped_share(feats, bounds)
        worst, share = max(shares.items(), key=lambda kv: kv[1])
        detail = ", ".join(f"{c} {s:.0%}" for c, s in shares.items())
        level = "WARN" if share > metrics.CLIP_ALERT else "OK"
        checks.append((level, f"Input range: share of {len(feats)} upcoming matches outside "
                              f"the training range (about 2% is normal): {detail}."))
    return checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=None)
    version = parser.parse_args().version or settings.model_version

    print(f"Monitoring report: model {version}, {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC\n")
    checks = run_checks(version)
    for level, message in checks:
        print(f"[{level:5}] {message}")
    sys.exit(1 if any(level == "WARN" for level, _ in checks) else 0)


if __name__ == "__main__":
    main()