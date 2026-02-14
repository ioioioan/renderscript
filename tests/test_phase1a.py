from __future__ import annotations

import json

from renderscript.compiler import compile_file
from renderscript.validate import validate_file


def test_compile_and_validate_deterministic(tmp_path):
    src = tmp_path / "tiny.fountain"
    out1 = tmp_path / "one.rscript"
    out2 = tmp_path / "two.rscript"

    src.write_text(
        """Title: Tiny Test

INT. OFFICE - DAY
Alice enters.

EXT. STREET - NIGHT
She leaves.
""",
        encoding="utf-8",
    )

    compile_file(src, out1)
    ok, message = validate_file(out1)
    assert ok, message

    compile_file(src, out2)
    assert out1.read_text(encoding="utf-8") == out2.read_text(encoding="utf-8")

    compiled = json.loads(out1.read_text(encoding="utf-8"))
    assert compiled["rscript_version"] == "0.1"
    assert compiled["meta"]["source"]["format"] == "fountain"
    assert len(compiled["scenes"]) == 2
