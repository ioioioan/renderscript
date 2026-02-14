from __future__ import annotations

from pathlib import Path

from renderscript.compiler import compile_file
from renderscript.validate import validate_file


FIXTURES = [
    "t1_dialogue_attribution",
    "t2_character_continuity",
    "t3_prop_dependency",
    "t4_location_persistence",
]


def test_stage_a_golden_outputs(tmp_path: Path):
    for fixture in FIXTURES:
        source = Path("examples") / f"{fixture}.fountain"
        expected = Path("examples/expected") / f"{fixture}.rscript"
        out1 = tmp_path / f"{fixture}.one.rscript"
        out2 = tmp_path / f"{fixture}.two.rscript"

        ok, message = validate_file(expected)
        assert ok, f"{fixture} golden: {message}"

        compile_file(source, out1)
        compile_file(source, out2)

        ok, message = validate_file(out1)
        assert ok, f"{fixture}: {message}"

        expected_text = expected.read_text(encoding="utf-8")
        out1_text = out1.read_text(encoding="utf-8")
        out2_text = out2.read_text(encoding="utf-8")

        assert out1_text == out2_text, f"{fixture}: output changed between identical compiles"
        assert out1_text == expected_text, f"{fixture}: output diverges from golden file"
