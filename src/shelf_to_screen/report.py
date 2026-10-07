"""Run every analysis on the panel and write `report.md` plus CSV tables."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from shelf_to_screen.classify import grouped_cv
from shelf_to_screen.external import indicator_table, load_indicator
from shelf_to_screen.forecast import backtest, predict, summarise
from shelf_to_screen.regression import ConstantRegressor, fixed_effects, pooled_ols
from shelf_to_screen.totals import compare_published, jump_flags, median_per_capita, state_totals

OUTCOME = "log_visits_pc"
REGRESSORS = ["ebooks_pc", "elec_exp_pc"]
FORECAST_SERIES = ("print_books", "ebooks", "visits", "circ_digital")


def add_logs(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    out["log_visits_pc"] = np.log(out["visits_pc"].where(out["visits_pc"] > 0))
    out["log_circ_pc"] = np.log(out["circ_pc"].where(out["circ_pc"] > 0))
    return out


def run_all(panel: pd.DataFrame, seed: int = 42, published: pd.DataFrame | None = None,
            indicator: pd.DataFrame | None = None, outcome: str = OUTCOME, regressors=REGRESSORS) -> dict:
    panel = add_logs(panel)
    totals_all = state_totals(panel)
    totals_bal = state_totals(panel, balanced=True)
    res: dict = {
        "totals_all": totals_all,
        "totals_balanced": totals_bal,
        "medians": median_per_capita(panel),
        "jumps_all": jump_flags(totals_all),
        "jumps_balanced": jump_flags(totals_bal),
    }
    if published is not None:
        res["published"] = compare_published(totals_all, published)
    bt, fc = [], []
    for metric in FORECAST_SERIES:
        series = totals_bal[metric]
        if series.notna().sum() < 4:
            continue
        errors = backtest(series)
        summary = summarise(errors).assign(metric=metric)
        bt.append(summary)
        best = summary.iloc[0]["model"]
        nxt = predict(series.dropna().to_numpy(), best, 2)
        last = int(series.dropna().index.max())
        fc.append({"metric": metric, "model": best, f"{last + 1}": nxt[0], f"{last + 2}": nxt[1]})
    res["backtest"] = pd.concat(bt, ignore_index=True) if bt else pd.DataFrame()
    res["forecast"] = pd.DataFrame(fc)
    try:
        res["fixed_effects"] = fixed_effects(panel, outcome, list(regressors))
        res["pooled"] = pooled_ols(panel, outcome, list(regressors))
    except (ConstantRegressor, ValueError) as exc:
        res["regression_error"] = str(exc)
    try:
        cv = grouped_cv(panel, seed=seed)
        res["classifier"] = cv.groupby("model")["roc_auc"].agg(["mean", "std", "count"]).reset_index()
    except ValueError as exc:
        res["classifier_error"] = str(exc)
    if indicator is not None:
        series = load_indicator(indicator, totals_all.index)
        res["indicator"] = indicator_table(totals_all, series)
    return res


def _md(df: pd.DataFrame, floatfmt: str = "{:,.3f}") -> str:
    if df is None or df.empty:
        return "_none_"
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |", "|" + "---|" * len(cols)]
    for r in df.astype(object).itertuples(index=False):
        cells = []
        for v in r:
            if isinstance(v, (int, np.integer)) and not isinstance(v, bool):
                cells.append(str(v))
            elif isinstance(v, (float, np.floating)):
                cells.append("" if np.isnan(v) else (f"{v:,.0f}" if abs(v) >= 1000 else floatfmt.format(v)))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def markdown(res: dict, source: str, ingest_summary: str, panel_summary: str) -> str:
    lines = [
        "# shelf-to-screen report",
        "",
        f"- Data: `{source}`",
        "",
        "## Ingest",
        "",
        "```",
        ingest_summary,
        "```",
        "",
        "## Panel",
        "",
        "```",
        panel_summary,
        "```",
        "",
        "## State totals, all reporting libraries",
        "",
        _md(res["totals_all"].reset_index()),
        "",
        "## State totals, balanced panel (libraries in every year)",
        "",
        _md(res["totals_balanced"].reset_index()),
        "",
        "## Median per-capita values",
        "",
        _md(res["medians"].reset_index()),
        "",
        "## Year-over-year jumps above 50 % (check the source files)",
        "",
        "All libraries:",
        "",
        _md(res["jumps_all"]),
        "",
        "Balanced panel:",
        "",
        _md(res["jumps_balanced"]),
        "",
    ]
    if "published" in res:
        lines += ["## Comparison with published totals", "", _md(res["published"]), ""]
    lines += [
        "## Forecast backtest (balanced panel, one step ahead, rolling origin)",
        "",
        _md(res["backtest"]),
        "",
        "Forecast with the model that has the lowest backtest MAE:",
        "",
        _md(res["forecast"]),
        "",
        "## Panel regression",
        "",
    ]
    if "fixed_effects" in res:
        fe, po = res["fixed_effects"], res["pooled"]
        lines += [
            f"Outcome `{OUTCOME}`. Two-way fixed effects (library and year), errors clustered by library: "
            f"{fe.n} rows, {fe.clusters} libraries, within R2 {fe.r2_within:.3f}.",
            "",
            _md(fe.table),
            "",
            f"Pooled OLS for comparison ({po.n} rows):",
            "",
            _md(po.table),
            "",
        ]
    else:
        lines += [f"Not estimated: {res.get('regression_error')}", ""]
    lines += ["## Classifier: high digital share (grouped by library)", ""]
    lines += [_md(res["classifier"]) if "classifier" in res else f"Not estimated: {res.get('classifier_error')}", ""]
    if "indicator" in res:
        corr = res["indicator"].attrs["correlations"]
        lines += ["## External digital-reading indicator", "", _md(res["indicator"].reset_index()), "",
                  "Correlations over years (description only): " + ", ".join(f"{k} {v:.2f}" for k, v in corr.items()), ""]
    lines += [
        "## Limits",
        "",
        "- The regression gives within-library associations. It does not prove that e-books cause visits.",
        "- Libraries match across years by name, city and phone. A wrong link or a missed link changes the panel.",
        "- Fiscal years differ between libraries. The year in a file name is the reporting year.",
        "- Six yearly points are too few for a reliable forecast. Read the backtest errors first.",
    ]
    return "\n".join(lines) + "\n"


def write(out_dir, res: dict, source: str, ingest_summary: str, panel_summary: str, panel: pd.DataFrame) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.md").write_text(markdown(res, source, ingest_summary, panel_summary), encoding="utf-8")
    res["totals_all"].to_csv(out / "totals_all.csv")
    res["totals_balanced"].to_csv(out / "totals_balanced.csv")
    res["backtest"].to_csv(out / "backtest.csv", index=False)
    panel.to_csv(out / "panel.csv", index=False)
    summary = {k: v.table.to_dict(orient="records") for k, v in res.items() if k in ("fixed_effects", "pooled")}
    (out / "regression.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    return out
