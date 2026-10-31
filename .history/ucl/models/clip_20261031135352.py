import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin


class QuantileClipper(BaseEstimator, TransformerMixin):
    """Clip chosen columns to the range seen in training, so a gap the model
    has barely seen can't be extrapolated into extreme odds."""

    def __init__(self, columns, lower: float = 0.01, upper: float = 0.99):
        self.columns = columns
        self.lower = lower
        self.upper = upper

    def fit(self, X, y=None):
        X = pd.DataFrame(X)
        self.bounds_ = {
            c: (float(X[c].quantile(self.lower)), float(X[c].quantile(self.upper)))
            for c in self.columns
        }
        return self

    def transform(self, X):
        X = pd.DataFrame(X).copy()
        for c, (lo, hi) in self.bounds_.items():
            X[c] = X[c].clip(lo, hi)
        return X