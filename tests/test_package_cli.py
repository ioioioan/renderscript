from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from renderscript import cli


BASE_REQUIRED_PATHS = [
    "rpack.json",
    "rpack.schema.json",
    "PACKAGE_MAP.md",
    "README.md",
    "CREATOR_GUIDE.pdf",
    "assets/ingredients_manifest.md",
    "prompts/asset_prompts.md",
    "assets/placeholder/characters/README.md",
    "assets/placeholder/locations/README.md",
    "assets/placeholder/styles/README.md",
    "assets/placeholder/props/README.md",
    "audio/voice_bible.md",
    "audio/dialogue_script.txt",
    "audio/sfx_cue_sheet.md",
    "edit/subtitles.srt",
    "shots/shot_list.csv",
    "bindings/bindings.csv",
    "rubric/scoring_sheet.csv",
]


def _required_paths(prompt_file: str) -> list[str]:
    return BASE_REQUIRED_PATHS + [prompt_file]


def _zip_contents(path: Path) -> dict[str, bytes]:
    with ZipFile(path, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def _csv_rows(raw: bytes) -> list[dict[str, str]]:
    import csv

    return list(csv.DictReader(StringIO(raw.decode("utf-8"))))


def _rpack_without_generated_at(raw: bytes) -> dict[str, object]:
    payload = json.loads(raw.decode("utf-8"))
    payload.pop("generated_at", None)
    return payload


def _pdf_text(raw: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return raw.decode("latin-1", errors="ignore")
    from io import BytesIO

    # pypdf expects a binary stream; keep fallback above for environments without pypdf.
    reader = PdfReader(BytesIO(raw))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


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
            "-o",
            str(out_two),
        ],
    )
    assert cli.main() == 0
    assert out_two.exists()

    required_paths = _required_paths("prompts/shot_prompts.md")
    with ZipFile(out_one, "r") as zf:
        assert zf.namelist() == required_paths

    contents_one = _zip_contents(out_one)
    contents_two = _zip_contents(out_two)
    assert set(contents_one.keys()) == set(required_paths)
    assert set(contents_two.keys()) == set(required_paths)

    for path in required_paths:
        if path == "rpack.json":
            assert _rpack_without_generated_at(contents_one[path]) == _rpack_without_generated_at(contents_two[path])
            continue
        assert contents_one[path] == contents_two[path]

    rpack = json.loads(contents_one["rpack.json"].decode("utf-8"))
    assert rpack["target_provider"] == "universal"
    assert rpack["generator"]["name"] == "RenderScript AI"
    assert "version" in rpack["generator"]
    assert isinstance(rpack["generated_at"], str)
    assert rpack["generated_at"].endswith("Z")
    assert 8 <= len(rpack["shots"]) <= 12

    shot_rows = _csv_rows(contents_one["shots/shot_list.csv"])
    bindings_rows = _csv_rows(contents_one["bindings/bindings.csv"])
    rubric_rows = _csv_rows(contents_one["rubric/scoring_sheet.csv"])
    prompt_text = contents_one["prompts/shot_prompts.md"].decode("utf-8")
    assert "prompts/universal_prompts.md" not in contents_one

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
    assert "IMPORTANT: NO ON-SCREEN TEXT. NO SUBTITLES. NO CAPTIONS. NO WATERMARKS. NO LOGOS." in prompt_text
    assert "Generate picture-only shots. Audio/dialogue will be added in post." in prompt_text
    assert prompt_text.count("No on-screen text or subtitles.") == len(rpack["shots"])

    package_map = contents_one["PACKAGE_MAP.md"].decode("utf-8")
    assert "Start here: CREATOR_GUIDE.pdf" in package_map
    assert "prompts/asset_prompts.md" in package_map
    assert "audio/voice_bible.md" in package_map
    assert "audio/dialogue_script.txt" in package_map
    assert "audio/sfx_cue_sheet.md" in package_map
    assert "edit/subtitles.srt" in package_map

    readme = contents_one["README.md"].decode("utf-8")
    assert "Generated by RenderScript AI v" in readme
    assert "Provider: universal" in readme

    asset_prompts = contents_one["prompts/asset_prompts.md"].decode("utf-8")
    assert "style_01_ref_01" in asset_prompts
    assert "loc_01_ref_01" in asset_prompts
    assert "assets/asset_prompts.md" not in contents_one

    assert len(contents_one["CREATOR_GUIDE.pdf"]) > 35000
    universal_pdf_text = _pdf_text(contents_one["CREATOR_GUIDE.pdf"])
    assert "Runway" not in universal_pdf_text
    assert "Workflow: Picture First, Audio in Post" in universal_pdf_text
    assert "If your tool generates subtitles anyway, reroll that shot." in universal_pdf_text

    assert contents_one["audio/voice_bible.md"].decode("utf-8").strip()
    dialogue_script = contents_one["audio/dialogue_script.txt"].decode("utf-8")
    assert "Dialogue Script (Audio in Post)" in dialogue_script
    sfx_sheet = contents_one["audio/sfx_cue_sheet.md"].decode("utf-8")
    assert "# SFX Cue Sheet" in sfx_sheet
    subtitles = contents_one["edit/subtitles.srt"].decode("utf-8")
    assert subtitles.lstrip().startswith("1")

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
    assert set(contents.keys()) == set(_required_paths("prompts/runway.gen4_image_refs_prompts.md"))


def test_package_output_directory_auto_names_zip_for_universal(
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
            "--project",
            "pilot",
            "-o",
            str(out_dir),
        ],
    )
    assert cli.main() == 0
    outputs = sorted(out_dir.glob("*.zip"))
    assert len(outputs) == 1
    assert outputs[0].name.startswith("pilot_scene_001_universal_renderpackage_v1")


def test_package_runway_provider_generates_runway_prompt_file(
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
            "-o",
            str(out_path),
        ],
    )
    assert cli.main() == 0
    contents = _zip_contents(out_path)
    assert "prompts/runway.gen4_image_refs_prompts.md" in contents
    assert "prompts/shot_prompts.md" not in contents
    assert "prompts/asset_prompts.md" in contents
    runway_prompt_text = contents["prompts/runway.gen4_image_refs_prompts.md"].decode("utf-8")
    assert "IMPORTANT: NO ON-SCREEN TEXT. NO SUBTITLES. NO CAPTIONS. NO WATERMARKS. NO LOGOS." in runway_prompt_text
    assert "Generate picture-only shots. Audio/dialogue will be added in post." in runway_prompt_text
    rpack = json.loads(contents["rpack.json"].decode("utf-8"))
    assert rpack["target_provider"] == "runway.gen4_image_refs"
    assert runway_prompt_text.count("No on-screen text or subtitles.") == len(rpack["shots"])
    runway_pdf_text = _pdf_text(contents["CREATOR_GUIDE.pdf"])
    assert "Runway" in runway_pdf_text
    assert len(contents["CREATOR_GUIDE.pdf"]) > 35000


def test_package_golden_expected_paths_universal_scene_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    source = Path("examples/realistic.fountain")
    out_path = tmp_path / "out.zip"
    monkeypatch.setattr(
        "sys.argv",
        [
            "renderscript",
            "package",
            str(source),
            "--scene",
            "1",
            "--provider",
            "universal",
            "-o",
            str(out_path),
        ],
    )
    assert cli.main() == 0
    expected_paths = {
        line.strip()
        for line in Path("tests/expected_package_paths.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    with ZipFile(out_path, "r") as zf:
        assert set(zf.namelist()) == expected_paths
        unpack_dir = tmp_path / "unpacked"
        zf.extractall(unpack_dir)
    assert (unpack_dir / "PACKAGE_MAP.md").read_text(encoding="utf-8").strip()
    assert (unpack_dir / "prompts/shot_prompts.md").read_text(encoding="utf-8").strip()
    assert not (unpack_dir / "prompts/universal_prompts.md").exists()
    assert (unpack_dir / "prompts/asset_prompts.md").read_text(encoding="utf-8").strip()
    assert (unpack_dir / "CREATOR_GUIDE.pdf").stat().st_size > 35000
