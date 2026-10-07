"""Synthetic yearly files in the layout of the Texas public library statistics export.

The libraries are fake. The files copy the format problems of the real exports, so the ingest
is tested offline: two digit groupings, `$` amounts with and without cents, `Yes`/`Y` flags,
phone formats, branch rows with no statistics, a renamed library with the same phone, and
libraries that do not report in each year.

Known effects: e-book holdings per capita grow each year, the digital share grows, 2020 has a
drop in visits for all libraries, and visits per capita rise by `EBOOK_EFFECT` for each e-book
per capita inside a library. Libraries with high fixed visits also hold more e-books, so a
pooled regression is biased and the fixed-effects regression is not.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

YEARS = (2018, 2019, 2020, 2021, 2022, 2023)
EBOOK_EFFECT = 0.8
HEADERS = [
    "Library Name", "Legal Service Area (Population Assignment)", "Start of Local Fiscal Year (LFY)",
    "End of Local Fiscal Year (LFY)", "Mail City", "Library Phone", "Total Staff Expenditures",
    "Print Material Expenditures", "Electronic Material Expenditures", "City/Library District Capital Revenue",
    "Total Capital Revenue", "Electronically Searchable  Catalog", "1% of Collection Published in Last Five Years?",
    "Books in Print", "Physical Audio Items", "E-books", "E-Audio", "Total Collection Items", "Annual Library Visits",
    "Registered Library Users", "Annual Circulation: All Other Ages Physical Items",
    "Annual Circulation: All Other Ages Digital Items", "Total Annual Circulation", "Public Internet Computers Available",
    "Number of Public Internet Computers", "Annual Number of Computer Uses", "Annual Website Visits",
    "Annual Number of Public Service Hours", "Annual Number Public Service Weeks",
]
CITIES = ["Alder", "Bluff", "Cedar Creek", "Dale", "Elm Point", "Fair Oaks", "Granite", "Harbor", "Iris", "Juniper"]


def group_digits(x: float, style: str, money: bool = False, cents: bool = False) -> str:
    """Format a number with `intl` (1,234,567) or `indian` (12,34,567) digit grouping."""
    whole = int(round(x))
    s = str(abs(whole))
    if style == "indian" and len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    else:
        s = f"{abs(whole):,}"
    if cents:
        s += ".00"
    return ("$" if money else "") + ("-" if whole < 0 else "") + s


def generate_panel(n_libraries: int = 150, seed: int = 0) -> pd.DataFrame:
    """The true values: one row for each library and year (before the file formatting)."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n_libraries):
        pop = float(np.round(rng.lognormal(9.3, 1.2)))
        alpha = rng.normal(0, 0.5)  # fixed visit level of the library
        ebook_base = max(0.02, 0.3 + 0.4 * alpha + rng.normal(0, 0.15))
        start = int(rng.integers(0, 2)) if rng.random() < 0.15 else 0
        stop = len(YEARS) - (int(rng.integers(1, 3)) if rng.random() < 0.1 else 0)
        fy_end_month = rng.choice([9, 12, 6, 8], p=[0.55, 0.3, 0.1, 0.05])
        for k, year in enumerate(YEARS[start:stop], start=start):
            ebooks_pc = ebook_base * (1 + 0.25 * k) * np.exp(rng.normal(0, 0.05))
            year_effect = {2020: -0.6, 2021: -0.3}.get(year, 0.0)
            visits_pc = np.exp(1.0 + alpha + year_effect + EBOOK_EFFECT * ebooks_pc + rng.normal(0, 0.08))
            share = float(np.clip(0.05 + 0.04 * k + 0.15 * (year == 2020) + rng.normal(0, 0.02), 0.01, 0.9))
            circ_total = pop * np.exp(1.2 + 0.6 * alpha + rng.normal(0, 0.1))
            rows.append(
                {
                    "lib": i, "year": year, "population": pop, "ebooks": ebooks_pc * pop, "visits": visits_pc * pop,
                    "circ_digital": round(circ_total * share), "circ_physical": round(circ_total * (1 - share)),
                    "print_books": pop * rng.uniform(1.5, 4), "eaudio": ebooks_pc * pop * 0.4,
                    "audio_items": pop * rng.uniform(0.02, 0.1), "staff_exp": pop * rng.uniform(5, 25),
                    "print_exp": pop * rng.uniform(0.5, 2), "elec_exp": pop * (0.2 + 0.1 * k) * rng.uniform(0.5, 1.5),
                    "computers": max(1, round(pop / rng.uniform(800, 3000))), "fy_end_month": int(fy_end_month),
                }
            )
    return pd.DataFrame(rows)


def write_files(out_dir: str | Path, n_libraries: int = 150, seed: int = 0) -> list[Path]:
    """Write one `<year>LibraryDataset.csv` file for each year. Returns the paths."""
    rng = np.random.default_rng(seed + 1)
    truth = generate_panel(n_libraries, seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = {i: f"{['North', 'South', 'East', 'West', 'Central'][i % 5]} {CITIES[i % 10]} Public Library {i:03d}" for i in truth["lib"].unique()}
    renamed = int(truth["lib"].min())
    paths = []
    for year in YEARS:
        rows = []
        indian = year in (2018, 2023)
        for _, r in truth[truth["year"] == year].iterrows():
            i = int(r["lib"])
            name = names[i]
            if i == renamed and year >= 2021:
                name = f"Memorial Library of {CITIES[i % 10]}"
            phone_digits = f"{325 + i % 600:03d}{(5550000 + i * 37) % 10_000_000:07d}"
            phone = f"({phone_digits[:3]}) {phone_digits[3:6]}-{phone_digits[6:]}" if year == 2023 else phone_digits
            m = int(r["fy_end_month"])
            end = pd.Timestamp(year, m, 1) + pd.offsets.MonthEnd(0)
            start = (end - pd.DateOffset(years=1) + pd.Timedelta(days=1))
            fmt = (lambda x, money=False: group_digits(x, "indian" if indian else "intl", money, cents=year == 2023))
            flag = "Y" if year >= 2022 else "Yes"
            coll = r["print_books"] + r["audio_items"] + r["ebooks"] + r["eaudio"]
            rows.append([
                name, fmt(r["population"]), start.strftime("%m-%d-%Y"), end.strftime("%m/%d/%Y"),
                CITIES[i % 10], phone, fmt(r["staff_exp"], True), fmt(r["print_exp"], True), fmt(r["elec_exp"], True),
                fmt(0, True), fmt(0, True), flag, flag, fmt(r["print_books"]), fmt(r["audio_items"]), fmt(r["ebooks"]),
                fmt(r["eaudio"]), fmt(coll), fmt(r["visits"]), fmt(r["population"] * 0.4),
                fmt(r["circ_physical"]), fmt(r["circ_digital"]), fmt(r["circ_physical"] + r["circ_digital"]),
                flag, str(int(r["computers"])), fmt(r["computers"] * 900), fmt(r["population"] * 1.5),
                fmt(2400), "52",
            ])
            if year in (2019, 2020) and rng.random() < 0.3:
                rows.append([f"{name} Branch", "", "", "", CITIES[i % 10], f"{phone_digits[:-1]}9"] + [""] * 23)
        path = out / f"{year}LibraryDataset.csv"
        pd.DataFrame(rows, columns=HEADERS).to_csv(path, index=False, encoding="utf-8-sig")
        paths.append(path)
    return paths
