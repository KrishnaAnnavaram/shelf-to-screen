"""Two-way fixed-effects regression with standard errors clustered by library.

The library effects remove fixed differences between libraries (size, region, history). The
year effects remove changes that hit all libraries in a year (for example 2020). The result is
a within-library association, not a causal effect.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


class ConstantRegressor(ValueError):
    """A regressor has no variation left (for example a column of zeros)."""


@dataclass
class RegressionResult:
    table: pd.DataFrame
    n: int
    clusters: int
    r2_within: float
    kind: str


def demean_two_way(df: pd.DataFrame, cols: list[str], entity: str, time: str, tol: float = 1e-10,
                   max_iter: int = 500) -> pd.DataFrame:
    """Remove entity and time means by alternating projections (works for an unbalanced panel)."""
    out = df[cols].astype(float).copy()
    for _ in range(max_iter):
        before = out.to_numpy().copy()
        out = out - out.groupby(df[entity]).transform("mean")
        out = out - out.groupby(df[time]).transform("mean")
        if np.max(np.abs(out.to_numpy() - before)) < tol:
            break
    return out


def _cluster_se(X: np.ndarray, u: np.ndarray, groups: np.ndarray, k: int) -> np.ndarray:
    n = X.shape[0]
    bread = np.linalg.inv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(groups):
        s = X[groups == g].T @ u[groups == g]
        meat += np.outer(s, s)
    G = len(np.unique(groups))
    c = G / (G - 1) * (n - 1) / max(n - k, 1)
    return np.sqrt(np.clip(np.diag(c * bread @ meat @ bread), 0, None))


def _table(names, beta, se, df_t) -> pd.DataFrame:
    with np.errstate(divide="ignore", invalid="ignore"):
        t = beta / se
    q = stats.t.ppf(0.975, df_t)
    return pd.DataFrame({"term": names, "coef": beta, "se": se, "ci_low": beta - q * se, "ci_high": beta + q * se,
                         "p_value": 2 * stats.t.sf(np.abs(t), df_t)})


def fixed_effects(panel: pd.DataFrame, outcome: str, regressors: list[str], entity: str = "library_id",
                  time: str = "file_year") -> RegressionResult:
    cols = [outcome, *regressors]
    df = panel.dropna(subset=cols).copy()
    counts = df.groupby(entity)[time].transform("count")
    df = df[counts >= 2]
    if df[entity].nunique() < 3:
        raise ValueError("need at least 3 libraries with 2 or more years")
    dm = demean_two_way(df, cols, entity, time)
    X, y = dm[regressors].to_numpy(), dm[outcome].to_numpy()
    flat = [r for r, s in zip(regressors, X.std(axis=0)) if s < 1e-12]
    if flat:
        raise ConstantRegressor(f"no variation left in {flat}. A constant or all-zero column has no estimate")
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    u = y - X @ beta
    groups = df[entity].to_numpy()
    se = _cluster_se(X, u, groups, len(regressors))
    G = len(np.unique(groups))
    r2 = 1 - (u @ u) / (y @ y) if y @ y > 0 else 0.0
    return RegressionResult(_table(regressors, beta, se, G - 1), len(df), G, float(r2), "two-way fixed effects")


def pooled_ols(panel: pd.DataFrame, outcome: str, regressors: list[str], entity: str = "library_id") -> RegressionResult:
    """OLS with an intercept and no fixed effects, for comparison. Errors clustered by library."""
    df = panel.dropna(subset=[outcome, *regressors])
    X = np.column_stack([np.ones(len(df)), df[regressors].to_numpy(dtype=float)])
    if np.any(X[:, 1:].std(axis=0) < 1e-12):
        raise ConstantRegressor("a regressor is constant")
    y = df[outcome].to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    u = y - X @ beta
    groups = df[entity].to_numpy()
    se = _cluster_se(X, u, groups, X.shape[1])
    G = len(np.unique(groups))
    r2 = 1 - (u @ u) / np.sum((y - y.mean()) ** 2)
    return RegressionResult(_table(["intercept", *regressors], beta, se, G - 1), len(df), G, float(r2), "pooled OLS")
