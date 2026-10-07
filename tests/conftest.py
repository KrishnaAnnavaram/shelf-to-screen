import os

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "2")

import pytest  # noqa: E402

from shelf_to_screen.ingest import read_folder  # noqa: E402
from shelf_to_screen.panel import build_panel  # noqa: E402
from shelf_to_screen.synthetic import write_files  # noqa: E402


@pytest.fixture(scope="session")
def files(tmp_path_factory):
    folder = tmp_path_factory.mktemp("libs")
    write_files(folder, n_libraries=80, seed=3)
    return folder


@pytest.fixture(scope="session")
def rows_reports(files):
    return read_folder(files)


@pytest.fixture(scope="session")
def panel_report(rows_reports):
    return build_panel(rows_reports[0])
