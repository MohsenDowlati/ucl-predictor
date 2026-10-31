import pandas as pd
import pytest
from ucl.models.walkforward import decay_weights, splits


def test_splits_never_train_on_the_future():
    df = pd.DataFrame({"season": [s for s in range(2013, 2020) for _ in range(3)]})
    out = list(splits(df, first_eval=2016))
    assert [s for s, _, _ in out] == [2016, 2017, 2018, 2019]
    for season, train, test in out:
        assert train.season.max() < season
        assert (test.season == season).all()
        assert train.season.min() == 2013


def test_decay_weights():
    w = decay_weights(pd.Series([2020, 2018, 2016]), half_life=2.0)
    assert w == pytest.approx([1.0, 0.5, 0.25])