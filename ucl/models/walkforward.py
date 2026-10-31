import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ucl.models.clip import QuantileClipper
from ucl.models.data import BINARY_FEATURES, FEATURE_SETS, WARMUP_END, load_features
from ucl.models.evaluate import (
    CLASSES, paired_bootstrap, per_match_log_loss, reliability, scores)
from ucl.models.train import climatology, proba_hda

FIRST_EVAL = 2016      # 3 seasons of training data (2013-2015) before the first test block
C = 0.1                # fixed, from the earlier validation tuning
HALF_LIFE = 4.0        # seasons, for the recency-weighted variant
MODELS = {
    "elo_only": ("elo_only", None),
    "full": ("full", None),
    "full_recent": ("full", HALF_LIFE),
}


def splits(df: pd.DataFrame, first_eval: int):
    """Yield (season, train, test): train is strictly earlier seasons only."""
    for s in sorted(df.season.unique()):
        if s >= first_eval:
            yield int(s), df[df.season < s], df[df.season == s]


def decay_weights(season: pd.Series, half_life: float) -> np.ndarray:
    """Newest training season = 1; a season one half-life older = 0.5."""
    age = season.max() - season
    return (0.5 ** (age / half_life)).to_numpy()


def fit_model(cols, train: pd.DataFrame, half_life: float | None = None):
    clip_cols = [c for c in cols if c not in BINARY_FEATURES]
    model = make_pipeline(
        QuantileClipper(clip_cols), StandardScaler(), LogisticRegression(C=C, max_iter=1000))
    kwargs = {}
    if half_life:
        w = decay_weights(train.season, half_life)
        kwargs["logisticregression__sample_weight"] = w / w.mean()   # keep regularization comparable
    return model.fit(train[cols], train["result"], **kwargs)


def run() -> None:
    df = load_features()
    df = df[df.result.notna() & (df.season > WARMUP_END)]

    evals = []
    probas: dict[str, list[np.ndarray]] = {"climatology": [], **{k: [] for k in MODELS}}
    for season, train, test in splits(df, FIRST_EVAL):
        evals.append(test)
        probas["climatology"].append(climatology(train, len(test)))
        for name, (feature_set, half_life) in MODELS.items():
            cols = FEATURE_SETS[feature_set]
            model = fit_model(cols, train, half_life)
            probas[name].append(proba_hda(model, test[cols]))

    ev = pd.concat(evals, ignore_index=True)
    P = {name: np.vstack(parts) for name, parts in probas.items()}
    loss = {name: per_match_log_loss(ev.result, p) for name, p in P.items()}
    print(f"{len(ev)} evaluation matches, seasons {ev.season.min()}-{ev.season.max()} "
          f"(each predicted by a model trained only on earlier seasons)")

    by_season = pd.DataFrame(loss).assign(season=ev.season).groupby("season").mean().round(4)
    by_season.insert(0, "n", ev.groupby("season").size())
    print("\nLog loss by season (lower is better)")
    print(by_season.to_string())

    print("\nPooled scores")
    print(pd.DataFrame({k: scores(ev.result, p) for k, p in P.items()}).T.round(4).to_string())

    print("\nPaired differences, pooled (negative = first model is better)")
    for a, b in [("elo_only", "climatology"), ("full", "elo_only"), ("full_recent", "full")]:
        d, lo, hi = paired_bootstrap(loss[a], loss[b])
        print(f"  {a} vs {b}: {d:+.4f}  (95% CI {lo:+.4f} to {hi:+.4f})")

    print("\nHome-win reliability, full model, pooled")
    print(reliability(ev.result, P["full"], "H").to_string())
    print("\nDraw reliability, full model, pooled")
    print(reliability(ev.result, P["full"], "D").to_string())

    rates = pd.DataFrame({"season": ev.season})
    for i, c in enumerate(CLASSES):
        rates[f"actual_{c}"] = (ev.result == c).astype(float)
        rates[f"pred_{c}"] = P["full"][:, i]
    print("\nOutcome rates by season: actual vs full-model average prediction")
    print(rates.groupby("season").mean().round(3).to_string())


if __name__ == "__main__":
    run()