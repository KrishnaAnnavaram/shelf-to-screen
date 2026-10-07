"""External digital-reading indicators.

The prototype made a "Kindle sales" column from a book-sales file that covers publishing years
up to 2016, and its publisher filter had a different number of spaces. The column was all
zeros. `check_sales_proxy` finds both problems. `load_indicator` accepts a yearly indicator only
if it covers each panel year and is not constant.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd


class ProxyError(ValueError):
    """The external indicator cannot be used for these years."""


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def check_sales_proxy(books: pd.DataFrame, publisher: str, years, year_col: str = "Publishing Year",
                      publisher_col: str = "Publisher", sales_col: str = "gross sales") -> dict:
    """Report the coverage of a book-sales file for a publisher and the panel years."""
    for c in (year_col, publisher_col, sales_col):
        if c not in books.columns:
            raise ProxyError(f"book file misses the column {c!r}")
    exact = books[publisher_col].astype(str) == publisher
    loose = books[publisher_col].map(_norm) == _norm(publisher)
    year = pd.to_numeric(books[year_col], errors="coerce")
    rows = books[loose]
    covered = sorted(set(int(y) for y in year[loose].dropna()) & set(int(y) for y in years))
    info = {
        "exact_matches": int(exact.sum()),
        "whitespace_insensitive_matches": int(loose.sum()),
        "max_publishing_year": int(year.max()) if year.notna().any() else None,
        "panel_years_covered": covered,
        "sales_in_panel_years": float(pd.to_numeric(rows.loc[year[loose].isin(list(years)), sales_col], errors="coerce").sum()),
    }
    if not covered:
        raise ProxyError(
            f"the book file has no rows for {publisher!r} in the panel years {list(years)} "
            f"(latest publishing year {info['max_publishing_year']}). The proxy would be all zeros"
        )
    return info


def load_indicator(df: pd.DataFrame, years) -> pd.Series:
    """A yearly indicator (`year, value`) that covers each panel year and has variation."""
    if not {"year", "value"} <= set(df.columns):
        raise ProxyError("the indicator CSV needs the columns year and value")
    s = df.set_index(df["year"].astype(int))["value"].astype(float)
    missing = sorted(set(int(y) for y in years) - set(s.index))
    if missing:
        raise ProxyError(f"the indicator has no value for {missing}")
    s = s.loc[sorted(int(y) for y in years)]
    if s.std() == 0 or np.isnan(s.std()):
        raise ProxyError("the indicator is constant")
    return s


def indicator_table(totals: pd.DataFrame, indicator: pd.Series, metrics=("circ_digital", "circ_physical", "visits")) -> pd.DataFrame:
    """Yearly table and Pearson correlations. With about six years, this is description only."""
    table = totals[list(metrics)].join(indicator.rename("indicator"), how="inner")
    corr = {m: float(table[m].corr(table["indicator"])) for m in metrics}
    table.attrs["correlations"] = corr
    return table
