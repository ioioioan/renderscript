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


def test_prompt_target_universal_works(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    input_file = Path("examples/t1_dialogue_attribution.fountain")
    output_file = tmp_path / "universal.txt"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "prompt",
            str(input_file),
            "--target",
            "universal",
            "--mode",
            "structured",
            "-o",
            str(output_file),
        ],
    )
    assert cli.main() == 0
    assert output_file.exists()


def test_prompt_default_target_is_universal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    input_file = Path("examples/t1_dialogue_attribution.fountain")
    output_default = tmp_path / "default.txt"
    output_universal = tmp_path / "universal.txt"

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "prompt",
            str(input_file),
            "--mode",
            "structured",
            "-o",
            str(output_default),
        ],
    )
    assert cli.main() == 0

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "prompt",
            str(input_file),
            "--target",
            "universal",
            "--mode",
            "structured",
            "-o",
            str(output_universal),
        ],
    )
    assert cli.main() == 0
    assert output_default.read_text(encoding="utf-8") == output_universal.read_text(encoding="utf-8")


def test_prompt_target_sora_matches_universal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    input_file = Path("examples/t1_dialogue_attribution.fountain")
    output_universal = tmp_path / "universal.txt"
    output_sora = tmp_path / "sora.txt"

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "prompt",
            str(input_file),
            "--target",
            "universal",
            "--mode",
            "structured",
            "-o",
            str(output_universal),
        ],
    )
    assert cli.main() == 0

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
            str(output_sora),
        ],
    )
    assert cli.main() == 0

    assert output_universal.read_text(encoding="utf-8") == output_sora.read_text(encoding="utf-8")


def test_prompt_mode_natural_content_and_determinism(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    input_file = Path("examples/t1_dialogue_attribution.fountain")
    output_one = tmp_path / "natural.one.txt"
    output_two = tmp_path / "natural.two.txt"

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "prompt",
            str(input_file),
            "--target",
            "universal",
            "--mode",
            "natural",
            "-o",
            str(output_one),
        ],
    )
    assert cli.main() == 0

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "prompt",
            str(input_file),
            "--target",
            "universal",
            "--mode",
            "natural",
            "-o",
            str(output_two),
        ],
    )
    assert cli.main() == 0

    text_one = output_one.read_text(encoding="utf-8")
    text_two = output_two.read_text(encoding="utf-8")

    assert "Constraints:" in text_one
    assert "- Follow events in order." in text_one
    assert "- Do not invent new characters, locations, or props." in text_one
    assert "- Keep characters consistent." in text_one
    assert "- Keep each scene’s location consistent." in text_one
    assert "- If dialogue cannot be spoken, render the exact lines as subtitles." in text_one
    assert "INT. SERVER ROOM - NIGHT" in text_one
    assert "ALICE" in text_one and "BOB" in text_one
    assert "char_" not in text_one
    assert "Did you copy the drive?" in text_one
    assert "Yes." in text_one
    assert "Then move." in text_one
    assert text_one == text_two
