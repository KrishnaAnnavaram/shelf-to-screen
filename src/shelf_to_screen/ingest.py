"""Read one yearly statistics file into typed rows.

* Headers go through one mapping table. An unknown header is an error, never a silent miss.
* Numbers accept any digit grouping (`1,36,268` and `136,268` are the same), `$`, decimals
  and parentheses for negative values. A negative count is a missing value.
* Names and cities keep their inner spaces. Only the outer spaces and repeated spaces go.
* A row with a name and no statistics (service hours and weeks do not count) is a branch row.
* A row with no name is a summary row (for example a state total). The report counts both
  kinds, and the panel drops them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

HEADER_MAP = {
    "library name": "name",
    "legal service area (population assignment)": "population",
    "start of local fiscal year (lfy)": "fy_start",
    "end of local fiscal year (lfy)": "fy_end",
    "mail city": "city",
    "library phone": "phone",
    "total staff expenditures": "staff_exp",
    "print material expenditures": "print_exp",
    "electronic material expenditures": "elec_exp",
    "city/library district capital revenue": "city_capital_rev",
    "total capital revenue": "capital_rev",
    "electronically searchable catalog": "searchable_catalog",
    "1% of collection published in last five years?": "recent_collection",
    "books in print": "print_books",
    "physical audio items": "audio_items",
    "e-books": "ebooks",
    "e-audio": "eaudio",
    "total collection items": "collection_total",
    "annual library visits": "visits",
    "registered library users": "registered_users",
    "annual circulation: all other ages physical items": "circ_physical",
    "annual circulation: all other ages digital items": "circ_digital",
    "total annual circulation": "circ_total",
    "public internet computers available": "computers_available",
    "number of public internet computers": "computers",
    "annual number of computer uses": "computer_uses",
    "annual website visits": "website_visits",
    "annual number of public service hours": "service_hours",
    "annual number public service weeks": "service_weeks",
}
TEXT = ("name", "city", "phone")
DATES = ("fy_start", "fy_end")
FLAGS = ("searchable_catalog", "recent_collection", "computers_available")
NUMBERS = tuple(v for v in HEADER_MAP.values() if v not in TEXT + DATES + FLAGS)
REQUIRED = ("name", "city", "fy_end", "population", "circ_physical", "circ_digital", "circ_total", "visits")


class IngestError(ValueError):
    """A yearly file cannot be read."""


@dataclass
class FileReport:
    path: str
    year: int
    rows: int = 0
    branch_rows: int = 0
    summary_rows: int = 0
    bad_numbers: dict[str, int] = field(default_factory=dict)
    negative_numbers: dict[str, int] = field(default_factory=dict)
    bad_flags: dict[str, int] = field(default_factory=dict)
    bad_dates: int = 0

    def summary(self) -> str:
        def fmt(d):
            return ", ".join(f"{k}={v}" for k, v in sorted(d.items())) or "none"

        return (f"{Path(self.path).name}: year={self.year} rows={self.rows} branch_rows={self.branch_rows} "
                f"summary_rows={self.summary_rows} "
                f"bad_dates={self.bad_dates} bad_numbers: {fmt(self.bad_numbers)} | negative: "
                f"{fmt(self.negative_numbers)} | bad_flags: {fmt(self.bad_flags)}")


def normalise_header(h: str) -> str:
    h = str(h).replace("﻿", "")
    h = re.sub(r"[^\x20-\x7e]", "", h)  # decorative symbols such as a triangle
    return re.sub(r"\s+", " ", h).strip().lower()


def map_headers(columns) -> dict[str, str]:
    mapping, unknown = {}, []
    for col in columns:
        key = normalise_header(col)
        if key in HEADER_MAP:
            mapping[col] = HEADER_MAP[key]
        elif key and not key.startswith("unnamed"):
            unknown.append(col)
    if unknown:
        raise IngestError(f"unknown headers {unknown}. Add them to HEADER_MAP")
    missing = [c for c in REQUIRED if c not in mapping.values()]
    if missing:
        raise IngestError(f"missing required columns {missing}")
    return mapping


_NUM = re.compile(r"^\(?-?\d[\d,]*(\.\d+)?\)?$|^\(?-?\.\d+\)?$")


def parse_number(value) -> float:
    """`$1,94,513.00` -> 194513.0, `(12)` -> -12.0, empty or text -> NaN."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    s = str(value).strip().replace("$", "").replace(" ", "").replace(" ", "")
    if s in ("", "-", "--", "n/a", "N/A", "NA"):
        return np.nan
    if not _NUM.match(s):
        return np.nan
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace(",", "")
    try:
        x = float(s)
    except ValueError:
        return np.nan
    return -x if neg else x


def parse_flag(value) -> float:
    s = str(value).strip().lower() if value is not None else ""
    if s in ("y", "yes", "true", "1"):
        return 1.0
    if s in ("n", "no", "false", "0"):
        return 0.0
    return np.nan


def clean_text(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def year_from_path(path: str | Path) -> int:
    m = re.search(r"(19|20)\d{2}", Path(path).name)
    if not m:
        raise IngestError(f"no year in the file name {Path(path).name!r}")
    return int(m.group(0))


def read_year(path: str | Path, year: int | None = None) -> tuple[pd.DataFrame, FileReport]:
    year = year_from_path(path) if year is None else year
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    raw = raw.rename(columns=map_headers(raw.columns))
    rep = FileReport(str(path), year, rows=len(raw))
    out = pd.DataFrame({"file_year": year}, index=raw.index)
    for col in TEXT:
        out[col] = raw[col].map(clean_text) if col in raw else ""
    out["phone_digits"] = out["phone"].str.replace(r"\D", "", regex=True).str[-10:]
    for col in DATES:
        if col in raw:
            parsed = pd.to_datetime(raw[col].str.strip(), errors="coerce", format="mixed")
            rep.bad_dates += int((parsed.isna() & (raw[col].str.strip() != "")).sum())
            out[col] = parsed
        else:
            out[col] = pd.NaT
    for col in NUMBERS:
        if col not in raw:
            out[col] = np.nan
            continue
        text = raw[col].astype(str).str.strip()
        values = text.map(parse_number)
        bad = int((values.isna() & (text != "")).sum())
        if bad:
            rep.bad_numbers[col] = bad
        neg = int((values < 0).sum())
        if neg:
            rep.negative_numbers[col] = neg
        out[col] = values.where(values >= 0)
    for col in FLAGS:
        if col not in raw:
            out[col] = np.nan
            continue
        text = raw[col].astype(str).str.strip()
        values = text.map(parse_flag)
        bad = int((values.isna() & (text != "")).sum())
        if bad:
            rep.bad_flags[col] = bad
        out[col] = values
    stats_cols = [c for c in NUMBERS if c not in ("population", "service_hours", "service_weeks")]
    out["is_summary_row"] = (out["name"] == "") | out["name"].str.lower().str.startswith("total")
    out["is_branch_row"] = ~out["is_summary_row"] & out[stats_cols].isna().all(axis=1) & out["population"].isna()
    rep.branch_rows = int(out["is_branch_row"].sum())
    rep.summary_rows = int(out["is_summary_row"].sum())
    return out.reset_index(drop=True), rep


def read_folder(folder: str | Path, pattern: str = "*LibraryDataset.csv") -> tuple[pd.DataFrame, list[FileReport]]:
    files = sorted(Path(folder).glob(pattern))
    if not files:
        raise IngestError(f"no files match {pattern!r} in {folder}")
    frames, reports = [], []
    for f in files:
        df, rep = read_year(f)
        frames.append(df)
        reports.append(rep)
    years = [r.year for r in reports]
    if len(set(years)) != len(years):
        raise IngestError(f"two files have the same year: {years}")
    return pd.concat(frames, ignore_index=True), reports
