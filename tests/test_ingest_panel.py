"""Reference problems 3, 5 and 6: digit grouping, destructive cleaning, no stable IDs."""

import numpy as np
import pandas as pd
import pytest

from shelf_to_screen.ingest import (
    IngestError,
    clean_text,
    map_headers,
    normalise_header,
    parse_flag,
    parse_number,
    read_folder,
    read_year,
    year_from_path,
)
from shelf_to_screen.panel import assign_ids, build_panel, normalise_key
from shelf_to_screen.synthetic import HEADERS, generate_panel, group_digits


@pytest.mark.parametrize(
    "text, value",
    [("1,36,268", 136268), ("136,268", 136268), ("$19,45,137.00", 1945137), ("$1,945,137", 1945137),
     ("(1,200)", -1200), ("0.5", 0.5), ("12", 12)],
)
def test_any_digit_grouping_gives_the_same_number(text, value):
    assert parse_number(text) == pytest.approx(value)


@pytest.mark.parametrize("text", ["", "-", "abc", "1.2.3", None, "N/A"])
def test_bad_numbers_are_missing(text):
    assert np.isnan(parse_number(text))


def test_flags_and_text():
    assert parse_flag("Y") == 1.0 and parse_flag("Yes") == 1.0 and parse_flag("No") == 0.0
    assert np.isnan(parse_flag("15256")) and np.isnan(parse_flag("`"))
    assert clean_text("  Fort   Worth  Public Library ") == "Fort Worth Public Library"  # inner spaces stay


def test_headers_map_with_symbols_and_double_spaces():
    assert normalise_header("﻿►Books in Print ") == "books in print"
    mapping = map_headers(HEADERS)
    assert mapping["Electronically Searchable  Catalog"] == "searchable_catalog"
    with pytest.raises(IngestError, match="unknown headers"):
        map_headers(HEADERS + ["Mystery Column"])
    with pytest.raises(IngestError, match="missing required"):
        map_headers(HEADERS[1:])


def test_year_from_file_name(tmp_path):
    assert year_from_path("2021LibraryDataset.csv") == 2021
    with pytest.raises(IngestError):
        year_from_path("LibraryDataset.csv")
    with pytest.raises(IngestError, match="no files"):
        read_folder(tmp_path)


def test_group_digits_round_trip():
    for x in (5, 1234, 123456, 12345678):
        for style in ("intl", "indian"):
            assert parse_number(group_digits(x, style, money=True, cents=True)) == x
    assert group_digits(12345678, "indian") == "1,23,45,678"


def test_read_year_counts_branch_and_summary_rows(tmp_path):
    rows = [
        ["Alpha Library", "1,000", "10-01-2020", "09/30/2021", "Alder", "3255550000"] + ["5"] * 5 + ["Yes", "Yes"]
        + ["10"] * 10 + ["Yes", "2", "100", "50", "1000", "52"],
        ["Alpha Library Branch", "", "", "", "Alder", "3255550001"] + [""] * 21 + ["900", "52"],
        ["", "99,999"] + [""] * 4 + ["1"] * 23,
    ]
    pd.DataFrame(rows, columns=HEADERS).to_csv(tmp_path / "2021LibraryDataset.csv", index=False)
    df, rep = read_year(tmp_path / "2021LibraryDataset.csv")
    assert rep.branch_rows == 1 and rep.summary_rows == 1
    assert df.loc[0, "population"] == 1000 and df.loc[0, "searchable_catalog"] == 1.0
    assert df.loc[0, "fy_end"].year == 2021


def test_negative_counts_become_missing(tmp_path):
    row = ["A", "1,000", "", "12/31/2020", "X", "1"] + ["-1"] * 23
    pd.DataFrame([row], columns=HEADERS).to_csv(tmp_path / "2020LibraryDataset.csv", index=False)
    df, rep = read_year(tmp_path / "2020LibraryDataset.csv")
    assert np.isnan(df.loc[0, "visits"]) and rep.negative_numbers["visits"] == 1


def test_phone_links_a_renamed_library():
    rows = pd.DataFrame(
        {
            "name": ["Old Name Library", "New Name Library", "Other Library"],
            "city": ["Alder", "Alder", "Alder"],
            "phone_digits": ["3255550000", "3255550000", "3255551111"],
        }
    )
    ids, links = assign_ids(rows)
    assert links == 1 and ids[0] == ids[1] != ids[2]
    assert normalise_key("St. Mary's  Library", " Alder ") == "st mary s library|alder"


def test_panel_has_one_row_for_each_library_and_year(panel_report, rows_reports):
    panel, rep = panel_report
    assert not panel.duplicated(["library_id", "file_year"]).any()
    assert rep.branch_rows_dropped == sum(r.branch_rows for r in rows_reports[1]) > 0
    assert rep.phone_links >= 1  # the renamed synthetic library
    truth = generate_panel(80, seed=3)
    assert rep.libraries == truth["lib"].nunique()
    assert rep.rows == len(truth)
    assert rep.circ_mismatch == 0 and rep.fiscal_year_mismatch == 0


def test_values_match_the_truth(panel_report):
    panel, _ = panel_report
    truth = generate_panel(80, seed=3)
    assert panel.groupby("file_year")["circ_digital"].sum().to_numpy() == pytest.approx(
        truth.groupby("year")["circ_digital"].sum().to_numpy())
    assert (panel["digital_share"].dropna().between(0, 1)).all()


def test_duplicate_rows_keep_the_most_complete(rows_reports):
    rows = rows_reports[0]
    first = rows[~rows["is_branch_row"]].iloc[[0]].copy()
    first["visits"] = np.nan
    panel, rep = build_panel(pd.concat([rows, first], ignore_index=True))
    assert rep.duplicates_dropped == 1
    lib, year = panel.iloc[0][["library_id", "file_year"]]
    kept = panel[(panel["library_id"] == lib) & (panel["file_year"] == year)]
    assert kept["visits"].notna().all()
