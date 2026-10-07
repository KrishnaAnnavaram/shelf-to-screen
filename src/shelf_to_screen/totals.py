"""State series computed from the panel (never typed in), with checks against published totals."""

from __future__ import annotations

import numpy as np
import pandas as pd

SERIES = ("print_books", "ebooks", "eaudio", "visits", "circ_physical", "circ_digital", "circ_total", "elec_exp", "print_exp")
MEDIANS = ("circ_pc", "visits_pc", "ebooks_pc", "digital_share")


def state_totals(panel: pd.DataFrame, balanced: bool = False, metrics=SERIES) -> pd.DataFrame:
    """Sum of each metric for each year. `balanced=True` uses only libraries present in every year."""
    df = panel[panel["balanced"]] if balanced else panel
    out = df.groupby("file_year")[list(metrics)].sum(min_count=1)
    out.insert(0, "libraries", df.groupby("file_year")["library_id"].nunique())
    out.insert(1, "reporting_circ", df.groupby("file_year")["circ_total"].count())
    return out


def median_per_capita(panel: pd.DataFrame, metrics=MEDIANS) -> pd.DataFrame:
    return panel.groupby("file_year")[list(metrics)].median()


def jump_flags(totals: pd.DataFrame, limit: float = 0.5) -> pd.DataFrame:
    """Year-over-year changes larger than `limit` (50 %). A flag asks for a check of the source file."""
    rows = []
    for col in totals.columns:
        if col in ("libraries", "reporting_circ"):
            continue
        s = totals[col].astype(float)
        change = s.pct_change(fill_method=None)
        for year, c in change.items():
            if np.isfinite(c) and abs(c) > limit:
                rows.append({"year": int(year), "metric": col, "change": float(c)})
    return pd.DataFrame(rows, columns=["year", "metric", "change"])


def compare_published(totals: pd.DataFrame, published: pd.DataFrame, tolerance: float = 0.02) -> pd.DataFrame:
    """Compare computed totals with a CSV of published totals (`year, metric, value`)."""
    need = {"year", "metric", "value"}
    if need - set(published.columns):
        raise ValueError(f"published totals need the columns {sorted(need)}")
    rows = []
    for _, r in published.iterrows():
        year, metric = int(r["year"]), str(r["metric"])
        ours = float(totals.loc[year, metric]) if (year in totals.index and metric in totals.columns) else np.nan
        diff = (ours - float(r["value"])) / float(r["value"]) if r["value"] else np.nan
        rows.append({"year": year, "metric": metric, "published": float(r["value"]), "computed": ours,
                     "relative_difference": diff, "ok": bool(np.isfinite(diff) and abs(diff) <= tolerance)})
    return pd.DataFrame(rows)
