"""Reference problem 8: one command line, relative paths, no notebook state."""

import pandas as pd

from shelf_to_screen.cli import main
from shelf_to_screen.config import Settings, load_env_file


def test_settings(monkeypatch, tmp_path):
    monkeypatch.delenv("SHELF_DATA_DIR", raising=False)
    s = Settings.from_env()
    assert s.data_dir is None and s.file_pattern == "*LibraryDataset.csv"
    env = tmp_path / ".env"
    env.write_text("SHELF_SEED=9\n", encoding="utf-8")
    monkeypatch.delenv("SHELF_SEED", raising=False)
    assert load_env_file(env) == 1 and Settings.from_env().seed == 9


def test_cli_end_to_end(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("SHELF_DATA_DIR", raising=False)
    folder = tmp_path / "files"
    assert main(["synth", "--libraries", "40", "--seed", "1", "--out-dir", str(folder)]) == 0
    panel_csv = tmp_path / "panel.csv"
    assert main(["ingest", "--data-dir", str(folder), "--out", str(panel_csv)]) == 0
    assert len(pd.read_csv(panel_csv)) > 100
    for cmd in (["totals"], ["backtest", "--metric", "visits"], ["regress"], ["classify"]):
        assert main([*cmd, "--data-dir", str(folder)]) == 0
    out = tmp_path / "rep"
    pub = tmp_path / "pub.csv"
    pd.DataFrame({"year": [2018], "metric": ["visits"], "value": [1.0]}).to_csv(pub, index=False)
    monkeypatch.setenv("SHELF_PUBLISHED_TOTALS", str(pub))
    assert main(["report", "--libraries", "40", "--out", str(out)]) == 0
    report = (out / "report.md").read_text(encoding="utf-8")
    assert "Comparison with published totals" in report and "Two-way fixed effects" in report
    assert (out / "totals_balanced.csv").is_file() and (out / "regression.json").is_file()
    books = tmp_path / "books.csv"
    pd.DataFrame({"Publishing Year": [2016], "Publisher": ["Amazon Digital Services,  Inc."],
                  "gross sales": [5.0]}).to_csv(books, index=False)
    assert main(["proxy", str(books)]) == 1
    assert "all zeros" in capsys.readouterr().err
    assert main(["ingest", "--data-dir", str(tmp_path / "empty")]) == 1
