"""Library-by-year panel: stable IDs, one row for each library and year, checks and per-capita metrics.

The yearly files have no stable library ID. `assign_ids` uses the normalised name and city, and
it links two keys when they share a 10-digit phone number in the same city (a renamed library).
The code never deletes inner spaces of names and never caps values.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from shelf_to_screen.ingest import NUMBERS

PER_CAPITA = {
    "circ_pc": "circ_total",
    "circ_physical_pc": "circ_physical",
    "circ_digital_pc": "circ_digital",
    "visits_pc": "visits",
    "print_books_pc": "print_books",
    "ebooks_pc": "ebooks",
    "eaudio_pc": "eaudio",
    "staff_exp_pc": "staff_exp",
    "print_exp_pc": "print_exp",
    "elec_exp_pc": "elec_exp",
    "website_visits_pc": "website_visits",
}


@dataclass
class PanelReport:
    rows: int = 0
    branch_rows_dropped: int = 0
    summary_rows_dropped: int = 0
    duplicates_dropped: int = 0
    phone_links: int = 0
    libraries: int = 0
    balanced_libraries: int = 0
    rows_by_year: dict[int, int] = field(default_factory=dict)
    fiscal_year_mismatch: int = 0
    circ_mismatch: int = 0
    collection_mismatch: int = 0

    def summary(self) -> str:
        years = ", ".join(f"{y}: {n}" for y, n in sorted(self.rows_by_year.items()))
        return (f"rows={self.rows} libraries={self.libraries} balanced={self.balanced_libraries} "
                f"branch_rows_dropped={self.branch_rows_dropped} summary_rows_dropped={self.summary_rows_dropped} "
                f"duplicates_dropped={self.duplicates_dropped} "
                f"phone_links={self.phone_links} fiscal_year_mismatch={self.fiscal_year_mismatch} "
                f"circ_mismatch={self.circ_mismatch} collection_mismatch={self.collection_mismatch}\n"
                f"rows by year: {years}")


def normalise_key(name: str, city: str) -> str:
    def norm(s: str) -> str:
        s = re.sub(r"[^a-z0-9 ]", " ", str(s).lower())
        return re.sub(r"\s+", " ", s).strip()

    return f"{norm(name)}|{norm(city)}"


class _UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[max(ra, rb)] = min(ra, rb)
        return True


def assign_ids(rows: pd.DataFrame) -> tuple[pd.Series, int]:
    keys = [normalise_key(n, c) for n, c in zip(rows["name"], rows["city"])]
    uf = _UnionFind()
    for k in keys:
        uf.find(k)
    links = 0
    city = rows["city"].str.lower().str.strip()
    phone_ok = rows["phone_digits"].str.len() == 10
    seen: dict[tuple[str, str], str] = {}
    for k, ph, ct, ok in zip(keys, rows["phone_digits"], city, phone_ok):
        if not ok:
            continue
        other = seen.setdefault((ph, ct), k)
        if other != k and uf.union(other, k):
            links += 1
    roots = [uf.find(k) for k in keys]
    return pd.Series(roots, index=rows.index, name="library_id"), links


def build_panel(rows: pd.DataFrame) -> tuple[pd.DataFrame, PanelReport]:
    rep = PanelReport()
    rep.branch_rows_dropped = int(rows["is_branch_row"].sum())
    rep.summary_rows_dropped = int(rows["is_summary_row"].sum())
    df = rows[~rows["is_branch_row"] & ~rows["is_summary_row"]].copy()
    df["library_id"], rep.phone_links = assign_ids(df)

    df["n_values"] = df[list(NUMBERS)].notna().sum(axis=1)
    df = df.sort_values(["library_id", "file_year", "n_values"], ascending=[True, True, False])
    dup = df.duplicated(["library_id", "file_year"], keep="first")
    rep.duplicates_dropped = int(dup.sum())
    df = df[~dup].drop(columns="n_values")

    df["fy_end_year"] = df["fy_end"].dt.year
    rep.fiscal_year_mismatch = int((df["fy_end_year"].notna() & (df["fy_end_year"] != df["file_year"])).sum())
    df["fy_months"] = ((df["fy_end"] - df["fy_start"]).dt.days / 30.44).round()

    # the physical and digital columns cover "all other ages". The total also has the
    # circulation for children, so only a total below the two parts is an error.
    parts = df["circ_physical"] + df["circ_digital"]
    df["circ_mismatch"] = parts.notna() & df["circ_total"].notna() & (df["circ_total"] < 0.99 * parts)
    rep.circ_mismatch = int(df["circ_mismatch"].sum())
    coll = df[["print_books", "audio_items", "ebooks", "eaudio"]].sum(axis=1, min_count=4)
    df["collection_mismatch"] = coll.notna() & df["collection_total"].notna() & (df["collection_total"] < 0.99 * coll)
    rep.collection_mismatch = int(df["collection_mismatch"].sum())

    pop = df["population"].where(df["population"] > 0)
    for new, col in PER_CAPITA.items():
        df[new] = df[col] / pop
    df["computers_per_1k"] = 1000 * df["computers"] / pop
    df["digital_share"] = df["circ_digital"] / parts.where(parts > 0)

    years = sorted(df["file_year"].unique())
    per_lib = df.groupby("library_id")["file_year"].nunique()
    balanced = set(per_lib[per_lib == len(years)].index)
    df["balanced"] = df["library_id"].isin(balanced)
    rep.rows = len(df)
    rep.libraries = int(df["library_id"].nunique())
    rep.balanced_libraries = len(balanced)
    rep.rows_by_year = {int(y): int(n) for y, n in df.groupby("file_year").size().items()}
    return df.reset_index(drop=True), rep
