from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from renderscript import cli


REQUIRED_PATHS = [
    "rpack.json",
    "README.md",
    "assets/ingredients_manifest.md",
    "shots/shot_list.csv",
    "bindings/bindings.csv",
    "prompts/runway.gen4_image_refs_prompts.md",
]


def _zip_contents(path: Path) -> dict[str, bytes]:
    with ZipFile(path, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


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
