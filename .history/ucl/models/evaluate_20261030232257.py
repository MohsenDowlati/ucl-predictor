import numpy as np
import pandas as pd

CLASSES = ["H", "D", "A"]      # fixed column order for every probability matrix


def per_match_log_loss(y, proba, eps: float = 1e-15) -> np.ndarray:
    idx = [CLASSES.index(v) for v in y]
    p = np.clip(np.asarray(proba)[np.arange(len(idx)), idx], eps, 1.0)
    return -np.log(p)


def brier(y, proba) -> float:
    onehot = np.array([[c == v for c in CLASSES] for v in y], dtype=float)
    return float(((np.asarray(proba) - onehot) ** 2).sum(axis=1).mean())


def scores(y, proba) -> dict:
    proba = np.asarray(proba)
    pred = np.array([CLASSES[i] for i in proba.argmax(axis=1)])
    return {
        "log_loss": float(per_match_log_loss(y, proba).mean()),
        "brier": brier(y, proba),
        "accuracy": float((pred == np.asarray(y)).mean()),
    }


def paired_bootstrap(loss_a, loss_b, n: int = 5000, seed: int = 0):
    """Mean of (loss_a - loss_b) with a 95% bootstrap interval. Negative = a is better."""
    diff = np.asarray(loss_a) - np.asarray(loss_b)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(n, len(diff)))
    means = diff[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(diff.mean()), float(lo), float(hi)


def reliability(y, proba, cls: str, bins=(0, .2, .3, .4, .5, .6, .7, 1.0)) -> pd.DataFrame:
    j = CLASSES.index(cls)
    df = pd.DataFrame({"p": np.asarray(proba)[:, j],
                       "hit": (np.asarray(y) == cls).astype(float)})
    df["bin"] = pd.cut(df.p, list(bins), include_lowest=True)
    return df.groupby("bin", observed=True).agg(
        n=("hit", "size"), predicted=("p", "mean"), actual=("hit", "mean")).round(3)