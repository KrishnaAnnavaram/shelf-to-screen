"""Command line: synth | ingest | totals | backtest | regress | classify | proxy | report."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import pandas as pd

from shelf_to_screen.classify import grouped_cv
from shelf_to_screen.config import Settings, load_env_file
from shelf_to_screen.external import ProxyError, check_sales_proxy
from shelf_to_screen.forecast import backtest, summarise
from shelf_to_screen.ingest import IngestError, read_folder
from shelf_to_screen.panel import build_panel
from shelf_to_screen.regression import fixed_effects, pooled_ols
from shelf_to_screen.report import OUTCOME, REGRESSORS, add_logs, run_all, write
from shelf_to_screen.synthetic import write_files
from shelf_to_screen.totals import state_totals


def _data_args(p):
    p.add_argument("--data-dir", help="folder with the yearly CSV files (default SHELF_DATA_DIR, else synthetic)")
    p.add_argument("--libraries", type=int, default=150, help="synthetic libraries when no folder is given")
    p.add_argument("--seed", type=int)


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="shelf-to-screen", description=__doc__)
    ap.add_argument("--env-file", default=".env")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("synth", help="write synthetic yearly files")
    p.add_argument("--libraries", type=int, default=150)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out-dir", default="data/synthetic")
    for name, text in (("ingest", "read the files, build the panel and print the reports"),
                       ("totals", "state totals for all libraries and the balanced panel"),
                       ("backtest", "rolling-origin backtest of the balanced state totals"),
                       ("regress", "two-way fixed-effects regression and pooled OLS"),
                       ("classify", "grouped CV of the digital-share classifier"),
                       ("report", "run everything and write the report folder")):
        p = sub.add_parser(name, help=text)
        _data_args(p)
        if name == "ingest":
            p.add_argument("--out", help="write the panel CSV here")
        if name == "backtest":
            p.add_argument("--metric", default="ebooks")
        if name == "regress":
            p.add_argument("--outcome", default=OUTCOME)
            p.add_argument("--regressors", default=",".join(REGRESSORS))
        if name == "report":
            p.add_argument("--out", help="report folder (default SHELF_OUTPUT or reports/latest)")
    p = sub.add_parser("proxy", help="check a book-sales file as a digital-reading proxy")
    p.add_argument("books_csv")
    p.add_argument("--publisher", default="Amazon Digital Services, Inc.")
    p.add_argument("--years", default="2018,2019,2020,2021,2022,2023")
    return ap


def _panel(args, settings: Settings):
    seed = settings.seed if args.seed is None else args.seed
    folder = args.data_dir or settings.data_dir
    if folder:
        rows, reports = read_folder(folder, settings.file_pattern)
        source = folder
    else:
        with tempfile.TemporaryDirectory() as tmp:
            write_files(tmp, args.libraries, seed)
            rows, reports = read_folder(tmp, "*LibraryDataset.csv")
        source = f"synthetic(libraries={args.libraries}, seed={seed})"
    panel, prep = build_panel(rows)
    ingest_summary = "\n".join(r.summary() for r in reports)
    print(f"data: {source}\n{ingest_summary}\npanel: {prep.summary()}", file=sys.stderr)
    return panel, source, ingest_summary, prep.summary(), seed


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_env_file(args.env_file)
    try:
        return _run(args, Settings.from_env())
    except (IngestError, ProxyError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run(args, settings: Settings) -> int:
    if args.cmd == "synth":
        paths = write_files(args.out_dir, args.libraries, args.seed)
        print(f"wrote {len(paths)} files to {args.out_dir}")
        return 0
    if args.cmd == "proxy":
        books = pd.read_csv(args.books_csv)
        years = [int(y) for y in args.years.split(",")]
        print(check_sales_proxy(books, args.publisher, years))
        return 0

    panel, source, ing, pan, seed = _panel(args, settings)
    pd.set_option("display.width", 200)
    if args.cmd == "ingest":
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            panel.to_csv(args.out, index=False)
            print(f"wrote {len(panel)} rows to {args.out}")
        return 0
    if args.cmd == "totals":
        print("all libraries:\n" + state_totals(panel).to_string(float_format=lambda x: f"{x:,.0f}"))
        print("balanced panel:\n" + state_totals(panel, balanced=True).to_string(float_format=lambda x: f"{x:,.0f}"))
        return 0
    if args.cmd == "backtest":
        errors = backtest(state_totals(panel, balanced=True)[args.metric])
        print(errors.to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
        print(summarise(errors).to_string(index=False, float_format=lambda x: f"{x:,.3f}"))
        return 0
    if args.cmd == "regress":
        regs = [r.strip() for r in args.regressors.split(",") if r.strip()]
        df = add_logs(panel)
        for res in (fixed_effects(df, args.outcome, regs), pooled_ols(df, args.outcome, regs)):
            print(f"{res.kind}: n={res.n} libraries={res.clusters} r2={res.r2_within:.3f}")
            print(res.table.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        return 0
    if args.cmd == "classify":
        cv = grouped_cv(panel, seed=seed)
        print(cv.groupby("model")["roc_auc"].agg(["mean", "std", "count"]).to_string(float_format=lambda x: f"{x:.3f}"))
        return 0
    if args.cmd == "report":
        published = pd.read_csv(settings.published_totals) if settings.published_totals else None
        indicator = pd.read_csv(settings.indicator_csv) if settings.indicator_csv else None
        res = run_all(panel, seed, published, indicator)
        out = write(args.out or settings.output_dir, res, source, ing, pan, panel)
        if "fixed_effects" in res:
            print(res["fixed_effects"].table.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
        print(f"wrote {out / 'report.md'}")
        return 0
    return 2  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
