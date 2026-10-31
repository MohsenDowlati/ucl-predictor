import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ucl.models.data import FEATURE_SETS, FULL_FEATURES, load_features, split
from ucl.models.evaluate import (
    CLASSES,
    paired_bootstrap,
    per_match_log_loss,
    reliability,
    scores,
)

C_GRID = [0.01, 0.03, 0.1, 0.3, 1, 3, 10]
ARTIFACTS = Path("artifacts")


def fit(cols, fit_df, C):
    model = make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=1000))
    return model.fit(fit_df[cols], fit_df["result"])


def proba_hda(model, X) -> np.ndarray:
    p = model.predict_proba(X)
    return p[:, [list(model.classes_).index(c) for c in CLASSES]]


def climatology(fit_df, n: int) -> np.ndarray:
    freq = fit_df.result.value_counts(normalize=True).reindex(CLASSES, fill_value=0).to_numpy()
    return np.tile(freq, (n, 1))


def tune(cols, train, val) -> float:
    """Pick C by validation log loss. The test set is never used here."""
    results = {}
    for C in C_GRID:
        m = fit(cols, train, C)
        results[C] = scores(val.result, proba_hda(m, val[cols]))["log_loss"]
    return min(results, key=results.get)


def run_phase(fit_df, eval_df, Cs):
    probas = {"climatology": climatology(fit_df, len(eval_df))}
    models = {}
    for name, cols in FEATURE_SETS.items():
        models[name] = fit(cols, fit_df, Cs[name])
        probas[name] = proba_hda(models[name], eval_df[cols])
    table = pd.DataFrame({k: scores(eval_df.result, p) for k, p in probas.items()}).T
    return models, probas, table.round(4)


def compare(y, probas, a: str, b: str) -> None:
    d, lo, hi = paired_bootstrap(per_match_log_loss(y, probas[a]),
                                 per_match_log_loss(y, probas[b]))
    print(f"  {a} vs {b}: {d:+.4f} log loss  (95% CI {lo:+.4f} to {hi:+.4f})")


def run() -> None:
    train, val, test = split(load_features())
    print(f"train {len(train)} matches (to {train.season.max()}), "
          f"val {len(val)} ({val.season.min()}-{val.season.max()}), "
          f"test {len(test)} ({test.season.min()}-{test.season.max()})")
    print("Class frequencies in train:",
          train.result.value_counts(normalize=True).round(3).to_dict())

    Cs = {name: tune(cols, train, val) for name, cols in FEATURE_SETS.items()}
    print("\nChosen regularization C (validation):", Cs)
    _, _, val_table = run_phase(train, val, Cs)
    print("\nValidation scores (models fit on train)")
    print(val_table.to_string())

    trainval = pd.concat([train, val])
    models, probas, test_table = run_phase(trainval, test, Cs)
    print(f"\nTEST scores, {len(test)} matches (models fit on train + validation)")
    print(test_table.to_string())
    print("  reference: uniform guess = log loss 1.0986, Brier 0.6667")

    print("\nPaired differences on test (negative = first model is better)")
    compare(test.result, probas, "elo_only", "climatology")
    compare(test.result, probas, "full", "elo_only")

    print("\nHome-win reliability, full model on test")
    print(reliability(test.result, probas["full"], "H").to_string())
    print("\nDraw reliability, full model on test")
    print(reliability(test.result, probas["full"], "D").to_string())

    final = models["full"]
    coefs = pd.DataFrame(final[-1].coef_, index=final.classes_, columns=FULL_FEATURES)
    print("\nStandardized coefficients (full model)")
    print(coefs.round(3).to_string())

    ARTIFACTS.mkdir(exist_ok=True)
    joblib.dump({
        "model": final, "features": FULL_FEATURES, "classes": CLASSES,
        "C": Cs["full"], "fit_through_season": int(trainval.season.max()),
    }, ARTIFACTS / "model_v1.joblib")
    (ARTIFACTS / "metrics_v1.json").write_text(json.dumps({
        "test": test_table.to_dict("index"),
        "validation": val_table.to_dict("index"),
        "C": {k: float(v) for k, v in Cs.items()},
    }, indent=2))
    print("\nSaved artifacts/model_v1.joblib and artifacts/metrics_v1.json")


if __name__ == "__main__":
    run()