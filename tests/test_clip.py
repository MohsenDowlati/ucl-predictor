import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ucl.models.clip import QuantileClipper


def test_clips_only_listed_columns_to_the_training_range():
    train = pd.DataFrame({"x": np.arange(101.0), "flag": [0] * 100 + [1]})
    clip = QuantileClipper(columns=["x"], lower=0.05, upper=0.95).fit(train)
    out = clip.transform(pd.DataFrame({"x": [-50.0, 50.0, 500.0], "flag": [1, 0, 1]}))
    assert out.x.tolist() == [5.0, 50.0, 95.0]
    assert out.flag.tolist() == [1, 0, 1]          # binary column untouched


def test_extreme_input_gets_the_same_odds_as_the_clip_bound():
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"elo_diff": rng.normal(0, 100, 500),
                      "neutral": rng.integers(0, 2, 500)})
    y = np.where(X.elo_diff + rng.normal(0, 100, 500) > 0, "H", "A")
    model = make_pipeline(
        QuantileClipper(["elo_diff"]), StandardScaler(), LogisticRegression()).fit(X, y)

    bound = model[0].bounds_["elo_diff"][1]
    proba = model.predict_proba(pd.DataFrame({"elo_diff": [bound, 10 * bound],
                                              "neutral": [0, 0]}))
    assert proba[0] == pytest.approx(proba[1])