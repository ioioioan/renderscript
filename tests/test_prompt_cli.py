from __future__ import annotations

from pathlib import Path

import pytest

from renderscript import cli


@pytest.mark.parametrize(
    ("fixture_name", "expected_name"),
    [
        ("t1_dialogue_attribution", "ALICE"),
        ("t2_character_continuity", "MARA"),
        ("t3_prop_dependency", None),
        ("t4_location_persistence", None),
    ],
)
def test_prompt_cli_examples_are_deterministic(
    fixture_name: str, expected_name: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    input_file = Path("examples") / f"{fixture_name}.fountain"
    output_one = tmp_path / f"{fixture_name}.one.txt"
    output_two = tmp_path / f"{fixture_name}.two.txt"

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "prompt",
            str(input_file),
            "--target",
            "sora",
            "--mode",
            "structured",
            "-o",
            str(output_one),
        ],
    )
    assert cli.main() == 0
    assert output_one.exists()

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "prompt",
            str(input_file),
            "--target",
            "sora",
            "--mode",
            "structured",
            "-o",
            str(output_two),
        ],
    )
    assert cli.main() == 0
    assert output_two.exists()

    text_one = output_one.read_text(encoding="utf-8")
    text_two = output_two.read_text(encoding="utf-8")

    assert "Scene 1" in text_one
    assert "char_" not in text_one
    if expected_name is not None:
        assert expected_name in text_one

    assert text_one == text_two
