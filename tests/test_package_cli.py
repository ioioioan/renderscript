from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from renderscript import cli


REQUIRED_PATHS = [
    "rpack.json",
    "rpack.schema.json",
    "README.md",
    "CREATOR_GUIDE.pdf",
    "assets/ingredients_manifest.md",
    "assets/placeholder/characters/README.md",
    "assets/placeholder/locations/README.md",
    "assets/placeholder/styles/README.md",
    "assets/placeholder/props/README.md",
    "shots/shot_list.csv",
    "bindings/bindings.csv",
    "rubric/scoring_sheet.csv",
    "prompts/runway.gen4_image_refs_prompts.md",
]


def _zip_contents(path: Path) -> dict[str, bytes]:
    with ZipFile(path, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def _csv_rows(raw: bytes) -> list[dict[str, str]]:
    import csv

    return list(csv.DictReader(StringIO(raw.decode("utf-8"))))


def test_package_generates_required_files_and_is_deterministic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_one = tmp_path / "out_one.zip"
    out_two = tmp_path / "out_two.zip"

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "runway.gen4_image_refs",
            "-o",
            str(out_one),
        ],
    )
    assert cli.main() == 0
    assert out_one.exists()

    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "runway.gen4_image_refs",
            "-o",
            str(out_two),
        ],
    )
    assert cli.main() == 0
    assert out_two.exists()

    with ZipFile(out_one, "r") as zf:
        assert zf.namelist() == REQUIRED_PATHS

    contents_one = _zip_contents(out_one)
    contents_two = _zip_contents(out_two)
    assert set(contents_one.keys()) == set(REQUIRED_PATHS)
    assert set(contents_two.keys()) == set(REQUIRED_PATHS)

    for path in REQUIRED_PATHS:
        assert contents_one[path] == contents_two[path]

    rpack = json.loads(contents_one["rpack.json"].decode("utf-8"))
    assert rpack["target_provider"] == "runway.gen4_image_refs"
    assert 8 <= len(rpack["shots"]) <= 12

    shot_rows = _csv_rows(contents_one["shots/shot_list.csv"])
    bindings_rows = _csv_rows(contents_one["bindings/bindings.csv"])
    rubric_rows = _csv_rows(contents_one["rubric/scoring_sheet.csv"])
    prompt_text = contents_one["prompts/runway.gen4_image_refs_prompts.md"].decode("utf-8")

    assert len(shot_rows) == len(rpack["shots"])
    assert len(bindings_rows) == len(rpack["shots"])
    assert len(rubric_rows) == len(rpack["shots"])

    shot_beats = {row["shot_id"]: row["beat"] for row in shot_rows}
    rubric_ids = {row["shot_id"] for row in rubric_rows}
    for row in bindings_rows:
        assert row["location_ref_ids"] == "loc_01_ref_01"
        assert row["style_ref_ids"] == "style_01_ref_01"
        if row["shot_id"] in shot_beats and ": " in shot_beats[row["shot_id"]]:
            assert row["character_ref_ids"], f"dialogue shot missing character refs: {row['shot_id']}"
    assert rubric_ids == {shot["shot_id"] for shot in rpack["shots"]}

    for shot in rpack["shots"]:
        assert shot["shot_id"] in prompt_text

    assert len(contents_one["CREATOR_GUIDE.pdf"]) > 5120

    for placeholder_path in [
        "assets/placeholder/characters/README.md",
        "assets/placeholder/locations/README.md",
        "assets/placeholder/styles/README.md",
        "assets/placeholder/props/README.md",
    ]:
        text = contents_one[placeholder_path].decode("utf-8")
        assert "char_A_ref_01" in text
        assert "Runway Gen-4 Image References supports up to 3 active references." in text


def test_package_errors_for_multi_scene_without_scene_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    source = Path("examples/realistic.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "runway.gen4_image_refs",
            "-o",
            str(out_path),
        ],
    )

    assert cli.main() == 1
    captured = capsys.readouterr()
    assert "v1 supports one scene; pass --scene to select" in captured.out


def test_package_errors_for_unsupported_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "invalid.provider",
            "-o",
            str(out_path),
        ],
    )

    assert cli.main() == 1
    captured = capsys.readouterr()
    assert "Unsupported provider: invalid.provider." in captured.out


def test_package_duration_override_applies_to_all_shots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "runway.gen4_image_refs",
            "--duration-s",
            "7",
            "-o",
            str(out_path),
        ],
    )
    assert cli.main() == 0
    contents = _zip_contents(out_path)
    shot_rows = _csv_rows(contents["shots/shot_list.csv"])
    assert shot_rows
    assert all(row["duration_s"] == "7" for row in shot_rows)


def test_package_output_directory_auto_names_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/t1_dialogue_attribution.fountain")
    out_dir = tmp_path / "packages"
    out_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--provider",
            "runway.gen4_image_refs",
            "--project",
            "pilot",
            "-o",
            str(out_dir),
        ],
    )
    assert cli.main() == 0
    outputs = sorted(out_dir.glob("*.zip"))
    assert len(outputs) == 1
    assert outputs[0].name.startswith("pilot_scene_001_runway_gen4_image_refs_renderpackage_v1")
    contents = _zip_contents(outputs[0])
    assert set(contents.keys()) == set(REQUIRED_PATHS)
