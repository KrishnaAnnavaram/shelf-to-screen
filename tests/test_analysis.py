"""Reference problems 1, 2, 4 and 7: zero proxy, hand-typed forecasts, classifier leakage, causal claims."""

import numpy as np
import pandas as pd
import pytest

from shelf_to_screen.classify import FEATURES, LeakyFeature, check_features, grouped_cv
from shelf_to_screen.external import ProxyError, check_sales_proxy, indicator_table, load_indicator
from shelf_to_screen.forecast import backtest, predict, summarise
from shelf_to_screen.regression import ConstantRegressor, demean_two_way, fixed_effects, pooled_ols
from shelf_to_screen.report import add_logs, run_all
from shelf_to_screen.synthetic import EBOOK_EFFECT, generate_panel
from shelf_to_screen.totals import compare_published, jump_flags, state_totals


def test_totals_come_from_the_panel(panel_report):
    panel, _ = panel_report
    t = state_totals(panel)
    assert t.loc[2018, "visits"] == pytest.approx(panel.loc[panel.file_year == 2018, "visits"].sum())
    b = state_totals(panel, balanced=True)
    assert b["libraries"].nunique() == 1  # the same libraries each year
    assert (b["libraries"] <= t["libraries"]).all()


def test_jump_flags_and_published_comparison():
    totals = pd.DataFrame({"libraries": [5, 5, 5], "visits": [100.0, 40.0, 45.0]}, index=[2019, 2020, 2021])
    flags = jump_flags(totals)
    assert flags.to_dict(orient="records") == [{"year": 2020, "metric": "visits", "change": pytest.approx(-0.6)}]
    pub = pd.DataFrame({"year": [2019, 2020], "metric": ["visits", "visits"], "value": [100.0, 50.0]})
    cmp = compare_published(totals, pub)
    assert cmp["ok"].tolist() == [True, False]
    with pytest.raises(ValueError):
        compare_published(totals, pub.drop(columns="value"))


def test_forecast_models_on_known_series():
    y = np.array([10.0, 12.0, 14.0, 16.0])
    assert predict(y, "naive", 2).tolist() == [16.0, 16.0]
    assert predict(y, "drift", 1)[0] == pytest.approx(18.0)
    assert predict(y, "linear", 1)[0] == pytest.approx(18.0)
    assert predict(y, "holt", 1)[0] == pytest.approx(18.0, abs=0.5)
    with pytest.raises(ValueError):
        predict(y, "prophet")


def test_backtest_uses_only_past_years():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0, 6.0], index=range(2018, 2024))
    errors = backtest(s)
    row = errors[(errors.year == 2021) & (errors.model == "naive")].iloc[0]
    assert row["forecast"] == 3.0  # 2021 is predicted from 2018-2020 only
    assert set(errors["year"]) == {2021, 2022, 2023}
    assert list(summarise(errors).columns) == ["model", "mae", "mape", "origins"]
    with pytest.raises(ValueError):
        backtest(s.iloc[:3])


def test_demeaning_removes_both_effects():
    df = pd.DataFrame({"e": [1, 1, 2, 2, 3], "t": [1, 2, 1, 2, 1], "x": [1.0, 2.0, 3.0, 5.0, 4.0]})
    dm = demean_two_way(df, ["x"], "e", "t")
    assert dm.groupby(df["e"])["x"].mean().abs().max() < 1e-8
    assert dm.groupby(df["t"])["x"].mean().abs().max() < 1e-8


def test_fixed_effects_remove_the_library_bias(panel_report):
    panel = add_logs(panel_report[0])
    fe = fixed_effects(panel, "log_visits_pc", ["ebooks_pc"])
    po = pooled_ols(panel, "log_visits_pc", ["ebooks_pc"])
    fe_b = fe.table.set_index("term").loc["ebooks_pc"]
    po_b = po.table.set_index("term").loc["ebooks_pc", "coef"]
    assert fe_b["ci_low"] < EBOOK_EFFECT < fe_b["ci_high"]
    assert po_b > EBOOK_EFFECT + 0.3  # the pooled estimate is biased by the fixed library level
    assert fe.clusters == panel["library_id"].nunique()


def test_all_zero_regressor_is_refused(panel_report):
    panel = add_logs(panel_report[0]).assign(kindle_sales=0.0)
    with pytest.raises(ConstantRegressor):
        fixed_effects(panel, "log_visits_pc", ["ebooks_pc", "kindle_sales"])
    with pytest.raises(ConstantRegressor):
        pooled_ols(panel, "log_visits_pc", ["kindle_sales"])


def test_sales_proxy_check_finds_the_zero_column():
    books = pd.DataFrame(
        {
            "Publishing Year": [2014, 2015, 2016],
            "Publisher": ["Amazon Digital Services,  Inc.", "Amazon Digital Services, Inc.", "Other"],
            "gross sales": [10.0, 20.0, 30.0],
        }
    )
    with pytest.raises(ProxyError, match="all zeros"):
        check_sales_proxy(books, "Amazon Digital Services, Inc.", range(2018, 2024))
    info = check_sales_proxy(books, "Amazon Digital Services, Inc.", [2014, 2015])
    assert info["exact_matches"] == 1 and info["whitespace_insensitive_matches"] == 2
    assert info["sales_in_panel_years"] == 30.0


def test_indicator_coverage(panel_report):
    totals = state_totals(panel_report[0])
    ind = pd.DataFrame({"year": range(2018, 2024), "value": [1, 2, 3, 4, 5, 6]})
    s = load_indicator(ind, totals.index)
    table = indicator_table(totals, s)
    assert set(table.attrs["correlations"]) == {"circ_digital", "circ_physical", "visits"}
    with pytest.raises(ProxyError, match="no value"):
        load_indicator(ind[ind.year < 2023], totals.index)
    with pytest.raises(ProxyError, match="constant"):
        load_indicator(ind.assign(value=0), totals.index)


def test_classifier_features_have_no_target_parts_or_ids(panel_report):
    check_features(FEATURES)
    for bad in (["circ_total"], ["population", "name"], ["phone"], ["digital_share"]):
        with pytest.raises(LeakyFeature):
            check_features(bad)
    cv = grouped_cv(panel_report[0], folds=3)
    assert set(cv["model"]) == {"base_rate", "logreg", "hgb"}
    assert cv.loc[cv.model == "hgb", "roc_auc"].between(0, 1).all()


def test_run_all_report_parts(panel_report):
    res = run_all(panel_report[0], seed=0)
    assert {"totals_all", "totals_balanced", "backtest", "forecast", "fixed_effects", "classifier"} <= set(res)
    assert set(res["forecast"]["metric"]) == {"print_books", "ebooks", "visits", "circ_digital"}


def test_truth_generator_is_seeded():
    pd.testing.assert_frame_equal(generate_panel(20, seed=1), generate_panel(20, seed=1))
