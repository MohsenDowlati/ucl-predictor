import argparse
from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy import select

from ucl.config import settings
from ucl.db.models import UPCOMING_STATUSES, Prediction, Team
from ucl.db.session import SessionLocal, engine, init_db

ARTIFACTS = Path("artifacts")
TOL = 1e-6     


def load_artifact(version: str) -> dict:
    path = ARTIFACTS / f"model_{version}.joblib"
    if not path.exists():
        raise SystemExit(f"{path} not found. Run: uv run python -m ucl.models.train")
    return joblib.load(path)


def predict_upcoming(features: pd.DataFrame, artifact: dict) -> pd.DataFrame:
    """match_id + p_home/p_draw/p_away for every not-yet-played match."""
    todo = features[features.result.isna() & features.status.isin(UPCOMING_STATUSES)]
    if todo.empty:
        return pd.DataFrame(columns=["match_id", "p_home", "p_draw", "p_away"])
    model = artifact["model"]
    proba = model.predict_proba(todo[artifact["features"]])
    order = [list(model.classes_).index(c) for c in artifact["classes"]]   # -> H, D, A
    proba = proba[:, order]
    return pd.DataFrame({
        "match_id": todo.match_id.to_numpy(),
        "p_home": proba[:, 0], "p_draw": proba[:, 1], "p_away": proba[:, 2],
    })


def store_predictions(session, preds: pd.DataFrame, version: str) -> tuple[int, int]:
    """Append a row only when a match's probabilities changed. Returns (added, unchanged)."""
    ids = [int(i) for i in preds.match_id]
    latest: dict[int, tuple[float, float, float]] = {}
    stmt = (select(Prediction)
            .where(Prediction.model_version == version, Prediction.match_id.in_(ids))
            .order_by(Prediction.id))
    for p in session.scalars(stmt):
        latest[p.match_id] = (p.p_home, p.p_draw, p.p_away)    # newest wins

    added = 0
    for r in preds.itertuples(index=False):
        new = (float(r.p_home), float(r.p_draw), float(r.p_away))
        old = latest.get(int(r.match_id))
        if old is not None and max(abs(a - b) for a, b in zip(new, old)) < TOL:
            continue
        session.add(Prediction(match_id=int(r.match_id), model_version=version,
                               p_home=new[0], p_draw=new[1], p_away=new[2]))
        added += 1
    session.commit()
    return added, len(preds) - added


def run(version: str | None = None) -> None:
    version = version or settings.model_version
    init_db()
    artifact = load_artifact(version)
    features = pd.read_sql("SELECT * FROM match_features", engine, parse_dates=["utc_date"])
    preds = predict_upcoming(features, artifact)

    with SessionLocal() as session:
        added, unchanged = store_predictions(session, preds, version)
        names = dict(session.execute(select(Team.id, Team.name)).all())

    print(f"Model {version}: {len(preds)} upcoming matches, "
          f"{added} new/changed predictions, {unchanged} unchanged")
    soon = (preds.merge(features[["match_id", "utc_date", "home_team_id", "away_team_id"]],
                        on="match_id").sort_values("utc_date").head(8))
    for r in soon.itertuples():
        print(f"  {r.utc_date:%Y-%m-%d}  {names[r.home_team_id]:<30} v {names[r.away_team_id]:<30}"
              f"  H {r.p_home:4.0%}  D {r.p_draw:4.0%}  A {r.p_away:4.0%}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=None)
    run(parser.parse_args().version)