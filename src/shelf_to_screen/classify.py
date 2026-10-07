"""Optional classifier: which libraries have a high digital share of circulation?

Rules that the prototype broke:
* no feature may contain a part of the target (no circulation column, no total);
* no name, phone or city code is a feature;
* the split keeps all years of one library in one fold (GroupKFold);
* the high/low limit comes from the training libraries of each fold.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = (
    "population",
    "staff_exp_pc",
    "print_exp_pc",
    "elec_exp_pc",
    "print_books_pc",
    "ebooks_pc",
    "eaudio_pc",
    "visits_pc",
    "computers_per_1k",
    "website_visits_pc",
    "service_hours",
    "file_year",
)
FORBIDDEN = ("circ", "digital_share", "name", "phone", "city", "library_id")


class LeakyFeature(AssertionError):
    """A feature contains the target or an identifier."""


def check_features(features) -> None:
    bad = [f for f in features if any(tok in f for tok in FORBIDDEN)]
    if bad:
        raise LeakyFeature(f"features that leak the target or an ID: {bad}")


def _models(seed: int):
    return {
        "logreg": Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()),
                            ("clf", LogisticRegression(max_iter=2000))]),
        "hgb": HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, random_state=seed),
    }


def grouped_cv(panel: pd.DataFrame, features=FEATURES, folds: int = 5, seed: int = 0) -> pd.DataFrame:
    check_features(features)
    df = panel.dropna(subset=["digital_share"]).reset_index(drop=True)
    groups = df["library_id"].to_numpy()
    X = df[list(features)].to_numpy(dtype=float)
    k = min(folds, len(np.unique(groups)))
    if k < 2:
        raise ValueError("need at least 2 libraries")
    rows = []
    for fold, (tr, te) in enumerate(GroupKFold(n_splits=k).split(X, groups=groups)):
        limit = float(np.median(df.loc[tr, "digital_share"]))
        y_tr = (df.loc[tr, "digital_share"] > limit).astype(int).to_numpy()
        y_te = (df.loc[te, "digital_share"] > limit).astype(int).to_numpy()
        if len(np.unique(y_te)) < 2 or len(np.unique(y_tr)) < 2:
            continue
        rows.append({"fold": fold, "model": "base_rate", "roc_auc": 0.5, "limit": limit})
        for name, model in _models(seed).items():
            model.fit(X[tr], y_tr)
            p = model.predict_proba(X[te])[:, 1]
            rows.append({"fold": fold, "model": name, "roc_auc": float(roc_auc_score(y_te, p)), "limit": limit})
        if set(groups[tr]) & set(groups[te]):
            raise AssertionError("a library is in train and test")
    return pd.DataFrame(rows)
