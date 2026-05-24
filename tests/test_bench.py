from __future__ import annotations

import csv
from pathlib import Path

from renderscript.cli import run_bench


def test_bench_examples_writes_valid_rows(tmp_path: Path):
    out_csv = tmp_path / "runs.csv"
    run_bench(input_dir=Path("examples"), out_csv=out_csv, label="phase1a")

    assert out_csv.exists()

    with out_csv.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    expected_rows = len(list(Path("examples").glob("*.fountain")))
    assert len(rows) == expected_rows
    assert all(row["schema_valid"] == "true" for row in rows)
