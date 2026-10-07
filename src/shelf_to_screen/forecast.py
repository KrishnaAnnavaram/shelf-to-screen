"""Small yearly series: baselines and a rolling-origin backtest.

Each model sees only the years before the year that it predicts. No regressor carries
information about the test years. With six yearly points, the backtest has few errors, so the
report shows the error of each origin, not only the mean.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

MODELS = ("naive", "drift", "linear", "holt")


def _holt(y: np.ndarray, horizon: int) -> np.ndarray:
    """Holt linear trend. Alpha and beta come from a grid search on the in-sample one-step errors."""
    best, best_sse = None, np.inf
    for a in np.linspace(0.1, 0.9, 9):
        for b in np.linspace(0.0, 0.5, 6):
            level, trend, sse = y[0], y[1] - y[0], 0.0
            for t in range(1, len(y)):
                pred = level + trend
                sse += (y[t] - pred) ** 2
                new_level = a * y[t] + (1 - a) * (level + trend)
                trend = b * (new_level - level) + (1 - b) * trend
                level = new_level
            if sse < best_sse:
                best, best_sse = (level, trend), sse
    level, trend = best
    return level + trend * np.arange(1, horizon + 1)


def predict(y, model: str, horizon: int = 1) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    if y.size < 2 or np.isnan(y).any():
        raise ValueError("need at least 2 values and no gaps")
    h = np.arange(1, horizon + 1)
    if model == "naive":
        return np.full(horizon, y[-1])
    if model == "drift":
        return y[-1] + h * (y[-1] - y[0]) / (y.size - 1)
    if model == "linear":
        t = np.arange(y.size)
        slope, intercept = np.polyfit(t, y, 1)
        return intercept + slope * (y.size - 1 + h)
    if model == "holt":
        return _holt(y, horizon)
    raise ValueError(f"unknown model {model!r}; choose from {MODELS}")


def backtest(series: pd.Series, models=MODELS, min_train: int = 3) -> pd.DataFrame:
    """One-step-ahead errors from each origin. `series` is indexed by year."""
    s = series.dropna().astype(float).sort_index()
    if len(s) <= min_train:
        raise ValueError(f"need more than {min_train} years for a backtest")
    rows = []
    for k in range(min_train, len(s)):
        train, actual = s.iloc[:k].to_numpy(), float(s.iloc[k])
        for m in models:
            if m == "holt" and k < 3:
                continue
            pred = float(predict(train, m, 1)[0])
            rows.append({"year": int(s.index[k]), "model": m, "actual": actual, "forecast": pred,
                         "abs_error": abs(pred - actual), "ape": abs(pred - actual) / abs(actual) if actual else np.nan})
    return pd.DataFrame(rows)


def summarise(errors: pd.DataFrame) -> pd.DataFrame:
    out = errors.groupby("model").agg(mae=("abs_error", "mean"), mape=("ape", "mean"), origins=("year", "count"))
    return out.sort_values("mae").reset_index()
