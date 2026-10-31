import pandas as pd

WARMUP_END = 2012      
TRAIN_END = 2020
VAL_END = 2022         # test = every season after this

BINARY_FEATURES = {"neutral", "is_knockout"}

ELO_FEATURES = ["elo_diff", "neutral"]
FULL_FEATURES = ELO_FEATURES + [
    "form_pts_diff", "form_gf_diff", "form_ga_diff", "is_knockout",
]
FEATURE_SETS = {"elo_only": ELO_FEATURES, "full": FULL_FEATURES}

def load_features() -> pd.DataFrame:
    from ucl.db.session import engine
    return pd.read_sql("SELECT * FROM match_features", engine, parse_dates=["utc_date"])


def split(df: pd.DataFrame):
    """Chronological train / validation / test, played matches only."""
    df = df[df.result.notna() & (df.season > WARMUP_END)]
    train = df[df.season <= TRAIN_END]
    val = df[(df.season > TRAIN_END) & (df.season <= VAL_END)]
    test = df[df.season > VAL_END]
    return train, val, test