from datetime import date

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from ucl.db.models import Base, Prediction
from ucl.models.predict import predict_upcoming, store_predictions
from ucl.pipelines.refresh import current_season


def tiny_artifact():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"elo_diff": rng.normal(0, 100, 300)})
    noisy = X.elo_diff + rng.normal(0, 150, 300)
    y = np.where(noisy > 40, "H", np.where(noisy < -40, "A", "D"))
    return {"model": LogisticRegression().fit(X, y),
            "features": ["elo_diff"], "classes": ["H", "D", "A"]}


def features_frame():
    return pd.DataFrame({
        "match_id": [1, 2, 3],
        "status": ["SCHEDULED", "FINISHED", "TIMED"],
        "result": [None, "H", None],
        "elo_diff": [50.0, 10.0, -80.0],
    })


def test_only_upcoming_matches_are_predicted_and_columns_are_in_hda_order():
    preds = predict_upcoming(features_frame(), tiny_artifact())
    assert preds.match_id.tolist() == [1, 3]
    assert preds[["p_home", "p_draw", "p_away"]].sum(axis=1).tolist() == pytest.approx([1, 1])

    assert preds.p_home[0] > preds.p_home[1]
    assert preds.p_away[0] < preds.p_away[1]


def test_store_is_idempotent_and_appends_only_on_change():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(engine)() as s:
        preds = predict_upcoming(features_frame(), tiny_artifact())
        assert store_predictions(s, preds, "v1") == (2, 0)
        assert store_predictions(s, preds, "v1") == (0, 2)

        changed = preds.copy()
        changed.loc[0, ["p_home", "p_draw", "p_away"]] = [0.5, 0.3, 0.2]
        assert store_predictions(s, changed, "v1") == (1, 1)
        assert s.scalar(select(func.count()).select_from(Prediction)) == 3


def test_current_season():
    assert current_season(date(2026, 10, 30)) == 2026
    assert current_season(date(2027, 2, 1)) == 2026
    assert current_season(date(2027, 7, 1)) == 2027