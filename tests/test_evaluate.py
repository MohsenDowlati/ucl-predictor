import numpy as np
import pandas as pd
import pytest

from ucl.models.data import TRAIN_END, VAL_END, WARMUP_END, split
from ucl.models.evaluate import paired_bootstrap, per_match_log_loss, scores

Y = ["H", "D", "A", "H"]


def test_uniform_prediction_scores():
    s = scores(Y, np.full((4, 3), 1 / 3))
    assert s["log_loss"] == pytest.approx(np.log(3))
    assert s["brier"] == pytest.approx(2 / 3)


def test_perfect_prediction_scores():
    proba = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 0]], dtype=float)
    s = scores(Y, proba)
    assert s["log_loss"] < 1e-9 and s["brier"] == 0 and s["accuracy"] == 1


def test_per_match_log_loss_uses_the_true_class():
    proba = np.array([[0.5, 0.3, 0.2], [0.5, 0.3, 0.2]])
    assert list(per_match_log_loss(["H", "D"], proba)) == pytest.approx(
        [-np.log(0.5), -np.log(0.3)])


def test_paired_bootstrap_constant_difference():
    b = np.random.default_rng(0).uniform(0.5, 1.5, 200)
    d, lo, hi = paired_bootstrap(b + 0.1, b)
    assert d == pytest.approx(0.1) and lo == pytest.approx(0.1) and hi == pytest.approx(0.1)


def test_paired_bootstrap_interval_covers_zero_when_models_are_equal_on_average():
    rng = np.random.default_rng(1)
    b = rng.uniform(0.5, 1.5, 300)
    noise = rng.normal(0, 0.3, 300)
    noise -= noise.mean()                       # mean difference is exactly zero
    _, lo, hi = paired_bootstrap(b + noise, b)
    assert lo < 0 < hi


def test_split_is_chronological_and_clean():
    df = pd.DataFrame([{"season": s, "result": r}
                       for s in range(2011, 2027) for r in ("H", "D", None)])
    train, val, test = split(df)
    assert train.season.min() == WARMUP_END + 1 and train.season.max() == TRAIN_END
    assert val.season.min() == TRAIN_END + 1 and val.season.max() == VAL_END
    assert test.season.min() == VAL_END + 1
    assert not pd.concat([train, val, test]).result.isna().any()