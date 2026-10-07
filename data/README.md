# data/

Git ignores every file in this folder except this README. Do not commit the yearly files.

## Real data: Texas public library statistics

| Item | Value |
|---|---|
| Name | Texas Public Library Statistics (annual report data, one export for each local fiscal year) |
| Publisher | Texas State Library and Archives Commission (TSLAC) |
| Source | <https://www.tsl.texas.gov/ldn/statistics> (library statistics pages) |
| Terms | Public data of a state agency. Read the terms on the source page. The files hold institution data only: library names, cities and main phone numbers |
| Expected files | `data/2018LibraryDataset.csv` to `data/2023LibraryDataset.csv` (any folder with `--data-dir` or `SHELF_DATA_DIR`. The pattern is `SHELF_FILE_PATTERN`) |

The year in each file name is the reporting year. Each file has the 29 columns below. The ingest maps
each header through `HEADER_MAP` in `src/shelf_to_screen/ingest.py`. An unknown header stops the ingest.

`Library Name`, `Legal Service Area (Population Assignment)`, `Start of Local Fiscal Year (LFY)`,
`End of Local Fiscal Year (LFY)`, `Mail City`, `Library Phone`, `Total Staff Expenditures`,
`Print Material Expenditures`, `Electronic Material Expenditures`, `City/Library District Capital Revenue`,
`Total Capital Revenue`, `Electronically Searchable Catalog`, `1% of Collection Published in Last Five Years?`,
`Books in Print`, `Physical Audio Items`, `E-books`, `E-Audio`, `Total Collection Items`, `Annual Library Visits`,
`Registered Library Users`, `Annual Circulation: All Other Ages Physical Items`,
`Annual Circulation: All Other Ages Digital Items`, `Total Annual Circulation`,
`Public Internet Computers Available`, `Number of Public Internet Computers`, `Annual Number of Computer Uses`,
`Annual Website Visits`, `Annual Number of Public Service Hours`, `Annual Number Public Service Weeks`.

Known format problems that the ingest handles: two digit groupings (`1,36,268` and `136,268`), `$` amounts
with and without cents, `Yes`/`Y` flags, branch rows with only service hours, a state total row with no name
(2022), negative values, and two phone formats.

## Optional files

| Setting | File | Columns |
|---|---|---|
| `SHELF_PUBLISHED_TOTALS` | Published state totals to check the computed totals | `year, metric, value` (metric = a panel column, for example `visits`) |
| `SHELF_INDICATOR_CSV` | A yearly digital-reading indicator that covers each panel year | `year, value` |

## Synthetic data (no download)

`shelf-to-screen synth --libraries 150 --out-dir data/synthetic` writes six fake yearly files with the same
layout and the same format problems. With no `--data-dir` and no `SHELF_DATA_DIR`, each command writes
them to a temporary folder and reads them back.
