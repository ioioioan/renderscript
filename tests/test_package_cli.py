from __future__ import annotations

import json
import re
from io import StringIO
from pathlib import Path
from zipfile import ZipFile

import pytest

from renderscript import cli


BASE_REQUIRED_PATHS = [
    "START_HERE.txt",
    "CREATOR_GUIDE.pdf",
    "PACKAGE_MAP.md",
    "shots/shot_list.csv",
    "shots/bindings.csv",
    "prompts/shot_prompts.md",
    "prompts/asset_prompts.md",
    "assets/ingredients_manifest.md",
    "assets/refs/styles/",
    "assets/refs/characters/",
    "assets/refs/locations/",
    "assets/refs/props/",
    "keepers/scoring_sheet.csv",
    "audio/voice_bible.md",
    "audio/dialogue_script.txt",
    "audio/sfx_cue_sheet.md",
    "edit_guide/subtitles.srt",
    "dev/rpack.json",
    "dev/provenance.json",
]


def _required_paths(*, include_runway_prompts: bool = False) -> list[str]:
    paths = list(BASE_REQUIRED_PATHS)
    if include_runway_prompts:
        paths.insert(paths.index("prompts/asset_prompts.md"), "prompts/runway.gen4_image_refs_prompts.md")
    return paths


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


def _provenance_without_generated_at(raw: bytes) -> dict[str, object]:
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


def _pdf_page_count(raw: bytes) -> int:
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return 0
    from io import BytesIO

    reader = PdfReader(BytesIO(raw))
    return len(reader.pages)


def _has_pypdf() -> bool:
    try:
        import pypdf  # type: ignore[import-not-found]
    except ModuleNotFoundError:
        return False
    return True


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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

    required_paths = _required_paths()
    with ZipFile(out_one, "r") as zf:
        assert zf.namelist() == required_paths

    contents_one = _zip_contents(out_one)
    contents_two = _zip_contents(out_two)
    assert set(contents_one.keys()) == set(required_paths)
    assert set(contents_two.keys()) == set(required_paths)

    for path in required_paths:
        if path == "dev/rpack.json":
            assert _rpack_without_generated_at(contents_one[path]) == _rpack_without_generated_at(contents_two[path])
            continue
        if path == "dev/provenance.json":
            assert _provenance_without_generated_at(contents_one[path]) == _provenance_without_generated_at(
                contents_two[path]
            )
            continue
        if path == "CREATOR_GUIDE.pdf":
            assert len(contents_one[path]) > 80000
            assert len(contents_two[path]) > 80000
            if _has_pypdf():
                assert _pdf_text(contents_one[path]) == _pdf_text(contents_two[path])
            continue
        assert contents_one[path] == contents_two[path]

    rpack = json.loads(contents_one["dev/rpack.json"].decode("utf-8"))
    provenance = json.loads(contents_one["dev/provenance.json"].decode("utf-8"))
    assert rpack["target_provider"] == "universal"
    assert rpack["generator"]["name"] == "RenderScript AI"
    assert "version" in rpack["generator"]
    assert isinstance(rpack["generated_at"], str)
    assert rpack["generated_at"].endswith("Z")
    assert 8 <= len(rpack["shots"]) <= 12
    assert rpack["debug"]["creator_guide"]["renderer_used"] == "html"
    assert isinstance(rpack["debug"]["creator_guide"]["error"], str)

    shot_rows = _csv_rows(contents_one["shots/shot_list.csv"])
    bindings_rows = _csv_rows(contents_one["shots/bindings.csv"])
    rubric_rows = _csv_rows(contents_one["keepers/scoring_sheet.csv"])
    prompt_text = contents_one["prompts/shot_prompts.md"].decode("utf-8")

    assert len(shot_rows) == len(rpack["shots"])
    assert len(bindings_rows) == len(rpack["shots"])
    assert len(rubric_rows) == len(rpack["shots"])
    assert list(shot_rows[0].keys()) == [
        "shot_id",
        "status",
        "beat",
        "shot_type",
        "camera",
        "description",
        "characters",
        "location",
        "style_ref",
        "duration_hint",
    ]
    assert list(bindings_rows[0].keys()) == [
        "shot_id",
        "character_refs",
        "location_refs",
        "style_refs",
        "prop_refs",
        "notes",
    ]
    assert list(rubric_rows[0].keys()) == [
        "shot_id",
        "keeper",
        "character_consistency",
        "location_consistency",
        "style_consistency",
        "note",
    ]

    shot_beats = {row["shot_id"]: row["beat"] for row in shot_rows}
    rubric_ids = {row["shot_id"] for row in rubric_rows}
    for row in bindings_rows:
        assert row["location_refs"] == "loc_01_ref_01"
        assert row["style_refs"] == "style_01_ref_01"
        if row["shot_id"] in shot_beats and ": " in shot_beats[row["shot_id"]]:
            assert row["character_refs"], f"dialogue shot missing character refs: {row['shot_id']}"
    assert rubric_ids == {shot["shot_id"] for shot in rpack["shots"]}

    for shot in rpack["shots"]:
        assert shot["shot_id"] in prompt_text
    assert "IMPORTANT: NO ON-SCREEN TEXT. NO SUBTITLES. NO CAPTIONS. NO WATERMARKS. NO LOGOS." in prompt_text
    assert "Generate picture-only shots. Audio/dialogue will be added in post." in prompt_text
    assert prompt_text.count("No on-screen text or subtitles.") == len(rpack["shots"])
    assert ".." not in prompt_text
    assert "?." not in prompt_text
    assert "!." not in prompt_text
    assert "  " not in prompt_text

    package_map = contents_one["PACKAGE_MAP.md"].decode("utf-8")
    assert "## 1) What to open first" in package_map
    assert "## 2) Where references go" in package_map
    assert "## 3) Where prompts live" in package_map
    assert "## 4) Where to track keepers" in package_map
    assert "## 5) Where audio files live" in package_map
    assert "## 6) Developer files" in package_map
    assert "shots/bindings.csv" in package_map
    assert "keepers/scoring_sheet.csv" in package_map
    assert "This package uses the Universal workflow." in package_map
    assert "Use `prompts/shot_prompts.md` to generate shots." in package_map
    assert "provider profile" not in package_map
    start_here = contents_one["START_HERE.txt"].decode("utf-8")
    assert "1. Read CREATOR_GUIDE.pdf" in start_here
    assert "2. Put reference images in assets/refs" in start_here
    assert "3. Generate takes using prompts" in start_here
    assert "4. Mark keepers in keepers/scoring_sheet.csv" in start_here

    assert provenance["provider"] == "universal"
    assert provenance["creator_guide"]["renderer_used"] == "html"

    asset_prompts = contents_one["prompts/asset_prompts.md"].decode("utf-8")
    assert "style_01_ref_01" in asset_prompts
    assert "loc_01_ref_01" in asset_prompts
    assert "assets/asset_prompts.md" not in contents_one

    assert len(contents_one["CREATOR_GUIDE.pdf"]) > 80000
    universal_pdf_text = _pdf_text(contents_one["CREATOR_GUIDE.pdf"])
    normalized_universal_pdf_text = _normalize_ws(universal_pdf_text)
    assert "Provider: Runway" not in normalized_universal_pdf_text
    assert "creator-guide-pad" not in normalized_universal_pdf_text
    assert "Page 1:" not in normalized_universal_pdf_text
    if _has_pypdf():
        assert "Keepers" in normalized_universal_pdf_text
        assert "Keeper Sheet" in normalized_universal_pdf_text
        assert "rough cut" in normalized_universal_pdf_text
        assert "Start \u2192 Refs \u2192 Takes \u2192 Keepers \u2192 Edit \u2192 Audio" in normalized_universal_pdf_text
        assert "Example scene" in normalized_universal_pdf_text
        assert "featuring Alice and Bob in Int. Server Room - Night." in normalized_universal_pdf_text
        assert "v0.1.0Page" not in universal_pdf_text
        assert _pdf_page_count(contents_one["CREATOR_GUIDE.pdf"]) == 5
    assert provenance["creator_guide"]["engine"] == "playwright"
    assert isinstance(provenance["creator_guide"]["error"], str)

    assert contents_one["audio/voice_bible.md"].decode("utf-8").strip()
    dialogue_script = contents_one["audio/dialogue_script.txt"].decode("utf-8")
    assert "Dialogue Script (Audio in Post)" in dialogue_script
    sfx_sheet = contents_one["audio/sfx_cue_sheet.md"].decode("utf-8")
    assert "# SFX Cue Sheet" in sfx_sheet
    subtitles = contents_one["edit_guide/subtitles.srt"].decode("utf-8")
    assert subtitles.lstrip().startswith("1")


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
    assert all(row["duration_hint"] == "7s" for row in shot_rows)


def test_dialogue_heavy_scene_uses_varied_end_coverage(
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
            "-o",
            str(out_path),
        ],
    )
    assert cli.main() == 0
    contents = _zip_contents(out_path)
    shot_rows = _csv_rows(contents["shots/shot_list.csv"])
    assert len(shot_rows) >= 8
    final_three = shot_rows[-3:]
    final_descriptions = [row["description"] for row in final_three]
    assert len(set(final_descriptions)) == len(final_descriptions)
    assert any("Reaction on" in description for description in final_descriptions)
    assert any("Two-shot coverage" in description for description in final_descriptions)
    assert final_three[0]["characters"] == "Alice"
    assert final_three[1]["characters"] == "Bob"
    assert final_three[2]["characters"] == "Alice;Bob"


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
    assert set(contents.keys()) == set(_required_paths(include_runway_prompts=True))


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
    assert "prompts/shot_prompts.md" in contents
    assert "prompts/asset_prompts.md" in contents
    runway_prompt_text = contents["prompts/runway.gen4_image_refs_prompts.md"].decode("utf-8")
    assert "IMPORTANT: NO ON-SCREEN TEXT. NO SUBTITLES. NO CAPTIONS. NO WATERMARKS. NO LOGOS." in runway_prompt_text
    assert "Generate picture-only shots. Audio/dialogue will be added in post." in runway_prompt_text
    rpack = json.loads(contents["dev/rpack.json"].decode("utf-8"))
    provenance = json.loads(contents["dev/provenance.json"].decode("utf-8"))
    assert rpack["target_provider"] == "runway.gen4_image_refs"
    assert rpack["debug"]["creator_guide"]["renderer_used"] == "html"
    assert runway_prompt_text.count("No on-screen text or subtitles.") == len(rpack["shots"])
    runway_pdf_text = _pdf_text(contents["CREATOR_GUIDE.pdf"])
    normalized_runway_pdf_text = _normalize_ws(runway_pdf_text)
    assert "Runway" in normalized_runway_pdf_text
    assert "creator-guide-pad" not in normalized_runway_pdf_text
    assert "Page 1:" not in normalized_runway_pdf_text
    if _has_pypdf():
        assert "Start \u2192 Refs \u2192 Takes \u2192 Keepers \u2192 Edit \u2192 Audio" in normalized_runway_pdf_text
        assert "rough cut" in normalized_runway_pdf_text
        assert "v0.1.0Page" not in runway_pdf_text
        assert _pdf_page_count(contents["CREATOR_GUIDE.pdf"]) == 5
    assert provenance["creator_guide"]["engine"] == "playwright"
    assert len(contents["CREATOR_GUIDE.pdf"]) > 80000


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
    assert (unpack_dir / "START_HERE.txt").read_text(encoding="utf-8").strip()
    assert (unpack_dir / "prompts/shot_prompts.md").read_text(encoding="utf-8").strip()
    assert not (unpack_dir / "prompts/runway.gen4_image_refs_prompts.md").exists()
    assert (unpack_dir / "prompts/asset_prompts.md").read_text(encoding="utf-8").strip()
    assert (unpack_dir / "CREATOR_GUIDE.pdf").stat().st_size > 80000
